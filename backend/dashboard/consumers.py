import asyncio
from contextlib import suppress

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .command_execution import ensure_interrupted_executions_failed, execution_group
from .models import CommandExecution
from .permissions import has_permission
from .ws_auth import user_from_token


class CommandExecutionConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.execution_id = int(self.scope["url_route"]["kwargs"]["execution_id"])
        if not await self.can_view():
            await self.close(code=4403)
            return
        self.group_name = execution_group(self.execution_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        self.expiry_task = asyncio.create_task(self.watch_auth())
        await self.send_json({"type": "snapshot", "execution": await self.snapshot()})

    async def disconnect(self, close_code):
        if hasattr(self, "expiry_task"):
            self.expiry_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.expiry_task
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # The command lifecycle is controlled by the authenticated HTTP API.
        return None

    async def execution_message(self, event):
        if not await user_from_token(self.scope.get("auth_token", "")):
            await self.close(code=4401)
            return
        await self.send_json(event["payload"])

    async def watch_auth(self):
        while True:
            await asyncio.sleep(1)
            if not await user_from_token(self.scope.get("auth_token", "")):
                await self.close(code=4401)
                return

    @database_sync_to_async
    def can_view(self):
        ensure_interrupted_executions_failed()
        execution = CommandExecution.objects.select_related("operator").filter(pk=self.execution_id).first()
        user = self.scope.get("user")
        return bool(execution and user and user.is_authenticated and has_permission(user, "command_execution.view") and (user.is_superuser or execution.operator_id == user.id))

    @database_sync_to_async
    def snapshot(self):
        execution = CommandExecution.objects.prefetch_related("outputs").get(pk=self.execution_id)
        return {
            "id": execution.id,
            "status": execution.status,
            "exit_code": execution.exit_code,
            "error_message": execution.error_message,
            "output_truncated": execution.output_truncated,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
            "outputs": [{
                "id": output.id, "stream": output.stream, "sequence": output.sequence,
                "content": output.content, "created_at": output.created_at.isoformat(),
            } for output in execution.outputs.all()],
        }
