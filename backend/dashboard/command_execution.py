import codecs
import logging
import shlex
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import CommandExecution, CommandExecutionOutput, OperationAudit
from .ssh import connect


logger = logging.getLogger(__name__)
EXECUTION_TIMEOUT_SECONDS = 600
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_USER_RUNNING = 2
MAX_GLOBAL_RUNNING = 10
ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("succeeded", "failed", "stopped", "timeout")

_executor = ThreadPoolExecutor(max_workers=MAX_GLOBAL_RUNNING, thread_name_prefix="filehub-command")
_active_channels = {}
_active_lock = threading.Lock()
_recovery_lock = threading.Lock()
_recovery_complete = False


def execution_group(execution_id):
    return f"command.execution.{execution_id}"


def _broadcast(execution_id, payload):
    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)(execution_group(execution_id), {"type": "execution.message", "payload": payload})


def _audit(execution, action, detail):
    try:
        OperationAudit.objects.create(
            operator=execution.operator,
            operator_name=execution.operator_name,
            operator_username=execution.operator_username,
            module="命令执行",
            action=action,
            object_name=f"{execution.host_name}（{execution.ip_address}）",
            ip_address=execution.requested_ip,
            detail=detail,
        )
    except Exception:
        logger.exception("Failed to persist command execution audit")


def build_remote_command(working_directory, command):
    return f"cd -- {shlex.quote(working_directory)} && {command}"


def start_execution(execution_id):
    transaction.on_commit(lambda: _executor.submit(_run_execution, execution_id))


def ensure_interrupted_executions_failed():
    global _recovery_complete
    if _recovery_complete:
        return
    with _recovery_lock:
        if _recovery_complete:
            return
        fail_interrupted_executions()
        _recovery_complete = True


def request_stop(execution_id):
    CommandExecution.objects.filter(pk=execution_id, status__in=ACTIVE_STATUSES).update(stop_requested=True)
    with _active_lock:
        channel = _active_channels.get(execution_id)
    if channel:
        try:
            channel.close()
        except Exception:
            pass


def _persist_output(execution_id, stream, sequence, content):
    output = CommandExecutionOutput.objects.create(
        execution_id=execution_id, stream=stream, sequence=sequence, content=content,
    )
    _broadcast(execution_id, {
        "type": "output", "id": output.id, "stream": stream,
        "sequence": sequence, "content": content, "created_at": output.created_at.isoformat(),
    })


def _finish(execution, status, exit_code=None, error_message=""):
    execution.status = status
    execution.exit_code = exit_code
    execution.error_message = error_message
    execution.finished_at = timezone.now()
    execution.save(update_fields=["status", "exit_code", "error_message", "finished_at"])
    detail = f"任务 #{execution.id}，{execution.mode}，路径 {execution.working_directory}"
    if exit_code is not None:
        detail += f"，退出码 {exit_code}"
    _audit(execution, {"succeeded": "成功", "failed": "失败", "stopped": "停止", "timeout": "超时"}[status], detail)
    _broadcast(execution.id, {
        "type": "status", "status": status, "exit_code": exit_code,
        "error_message": error_message, "finished_at": execution.finished_at.isoformat(),
        "output_truncated": execution.output_truncated,
    })


def _run_execution(execution_id):
    close_old_connections()
    client = None
    channel = None
    try:
        execution = CommandExecution.objects.select_related("file_config", "operator").get(pk=execution_id)
        if execution.stop_requested:
            _finish(execution, "stopped", error_message="命令在开始前已停止")
            return
        if not execution.file_config:
            _finish(execution, "failed", error_message="执行机器已被删除")
            return

        execution.status = "running"
        execution.started_at = timezone.now()
        execution.save(update_fields=["status", "started_at"])
        _broadcast(execution.id, {"type": "status", "status": "running", "started_at": execution.started_at.isoformat()})

        client = connect(execution.file_config)
        transport = client.get_transport()
        if not transport:
            raise ConnectionError("SSH 连接不可用")
        channel = transport.open_session(timeout=10)
        with _active_lock:
            _active_channels[execution.id] = channel
        channel.exec_command(build_remote_command(execution.working_directory, execution.command))

        decoders = {
            "stdout": codecs.getincrementaldecoder("utf-8")(errors="replace"),
            "stderr": codecs.getincrementaldecoder("utf-8")(errors="replace"),
        }
        sequence = 0
        stored_bytes = 0
        truncated = False
        started = time.monotonic()
        last_stop_check = 0.0

        while True:
            now = time.monotonic()
            if now - started >= EXECUTION_TIMEOUT_SECONDS:
                channel.close()
                _finish(execution, "timeout", error_message=f"命令执行超过 {EXECUTION_TIMEOUT_SECONDS // 60} 分钟")
                return
            if now - last_stop_check >= 0.5:
                last_stop_check = now
                if CommandExecution.objects.filter(pk=execution.id, stop_requested=True).exists():
                    channel.close()
                    _finish(execution, "stopped", error_message="用户停止了命令")
                    return

            received = False
            for stream, ready, receiver in (
                ("stdout", channel.recv_ready, channel.recv),
                ("stderr", channel.recv_stderr_ready, channel.recv_stderr),
            ):
                if not ready():
                    continue
                received = True
                data = receiver(32768)
                if not data:
                    continue
                if stored_bytes < MAX_OUTPUT_BYTES:
                    allowed = data[:MAX_OUTPUT_BYTES - stored_bytes]
                    stored_bytes += len(allowed)
                    content = decoders[stream].decode(allowed)
                    if content:
                        sequence += 1
                        _persist_output(execution.id, stream, sequence, content)
                if stored_bytes >= MAX_OUTPUT_BYTES and not truncated:
                    truncated = True
                    execution.output_truncated = True
                    execution.save(update_fields=["output_truncated"])
                    sequence += 1
                    _persist_output(execution.id, "stderr", sequence, "\n[输出已超过 2 MB，后续内容不再保存]\n")

            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                break
            if not received:
                time.sleep(0.05)

        for stream, decoder in decoders.items():
            content = decoder.decode(b"", final=True)
            if content and stored_bytes < MAX_OUTPUT_BYTES:
                sequence += 1
                _persist_output(execution.id, stream, sequence, content)
        execution.refresh_from_db(fields=["stop_requested"])
        if execution.stop_requested:
            _finish(execution, "stopped", error_message="用户停止了命令")
            return
        exit_code = channel.recv_exit_status()
        if exit_code == 0:
            _finish(execution, "succeeded", exit_code=0)
        else:
            _finish(execution, "failed", exit_code=exit_code, error_message=f"命令退出码为 {exit_code}")
    except Exception as error:
        logger.exception("Command execution %s failed", execution_id)
        try:
            execution = CommandExecution.objects.select_related("operator").get(pk=execution_id)
            if execution.status not in TERMINAL_STATUSES:
                status = "stopped" if execution.stop_requested else "failed"
                _finish(execution, status, error_message=str(error))
        except Exception:
            logger.exception("Failed to finalize command execution %s", execution_id)
    finally:
        with _active_lock:
            _active_channels.pop(execution_id, None)
        if channel:
            try:
                channel.close()
            except Exception:
                pass
        if client:
            client.close()
        close_old_connections()


def fail_interrupted_executions():
    now = timezone.now()
    interrupted = list(CommandExecution.objects.filter(status__in=ACTIVE_STATUSES))
    for execution in interrupted:
        execution.status = "failed"
        execution.error_message = "服务重启导致任务中断"
        execution.finished_at = now
    if interrupted:
        CommandExecution.objects.bulk_update(interrupted, ["status", "error_message", "finished_at"])
