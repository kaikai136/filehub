from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase, TransactionTestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .command_execution import build_remote_command
from .models import (
    Account, CommandExecution, CommandExecutionOutput, FileConfig, OperationAudit, RemoteFile, Role,
)


class CommandConstructionTests(SimpleTestCase):
    def test_working_directory_is_shell_quoted(self):
        self.assertEqual(build_remote_command("/srv/app data", "pwd"), "cd -- '/srv/app data' && pwd")
        self.assertEqual(build_remote_command("/tmp/user's", "pwd"), "cd -- '/tmp/user'\"'\"'s' && pwd")


class CommandExecutionApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("executor", password="secret")
        self.role = Role.objects.create(
            name="执行人员", code="command_runner",
            permissions=["command_execution.view", "command_execution.execute"],
        )
        self.user.roles.add(self.role)
        self.viewer = get_user_model().objects.create_user("command-viewer", password="secret")
        self.viewer_role = Role.objects.create(name="命令查看", code="command_viewer", permissions=["command_execution.view"])
        self.viewer.roles.add(self.viewer_role)
        self.account = Account.objects.create(name="SSH", username="root")
        self.config = FileConfig.objects.create(
            project="demo", host_name="node-01", ip_address="192.0.2.20",
            file_path="/srv/manifests", account=self.account,
        )
        self.file = RemoteFile.objects.create(
            file_config=self.config, project="demo", name="app.yaml", relative_path="k8s/app.yaml",
        )
        self.client.force_authenticate(self.user)

    def payload(self, **changes):
        result = {
            "mode": "shell", "file_config_id": self.config.id,
            "working_directory": "", "command": "pwd",
        }
        result.update(changes)
        return result

    @patch("dashboard.command_views.start_execution")
    def test_shell_defaults_to_root_and_creates_audit(self, start):
        response = self.client.post("/api/command-executions/", self.payload(), format="json")
        self.assertEqual(response.status_code, 201)
        execution = CommandExecution.objects.get()
        self.assertEqual(execution.working_directory, "/root")
        self.assertEqual(response.data["websocket_path"], f"/ws/command-executions/{execution.id}/")
        start.assert_called_once_with(execution.id)
        self.assertTrue(OperationAudit.objects.filter(module="命令执行", action="提交").exists())

    @patch("dashboard.command_views.start_execution")
    def test_k8s_file_builds_default_command_and_validates_ownership(self, start):
        response = self.client.post("/api/command-executions/", self.payload(
            mode="k8s", working_directory="/srv/manifests", command="", remote_file_id=self.file.id,
        ), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["command"], "kubectl apply -f /srv/manifests/k8s/app.yaml")
        self.assertEqual(response.data["file_path"], "/srv/manifests/k8s/app.yaml")

        other = FileConfig.objects.create(project="other", host_name="node-02", ip_address="192.0.2.21", account=self.account)
        wrong_file = RemoteFile.objects.create(file_config=other, project="other", name="bad.yaml", relative_path="bad.yaml")
        blocked = self.client.post("/api/command-executions/", self.payload(
            mode="k8s", working_directory="/root", command="kubectl get pods", remote_file_id=wrong_file.id,
        ), format="json")
        self.assertEqual(blocked.status_code, 400)

    @patch("dashboard.command_views.start_execution")
    def test_k8s_without_file_accepts_manual_command(self, start):
        response = self.client.post("/api/command-executions/", self.payload(
            mode="k8s", working_directory="/root", command="kubectl get pods",
        ), format="json")
        self.assertEqual(response.status_code, 201)

    def test_validation_rejects_missing_values_and_unsafe_input(self):
        self.assertEqual(self.client.post("/api/command-executions/", self.payload(command=""), format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/command-executions/", self.payload(mode="k8s", working_directory=""), format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/command-executions/", self.payload(working_directory="/root\n/tmp"), format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/command-executions/", self.payload(command="x" * 10001), format="json").status_code, 400)

    def test_viewer_can_list_but_cannot_execute(self):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get("/api/command-executions/").status_code, 200)
        self.assertEqual(self.client.post("/api/command-executions/", self.payload(), format="json").status_code, 403)

    @patch("dashboard.command_views.start_execution")
    def test_history_and_detail_are_private_except_for_superuser(self, start):
        created = self.client.post("/api/command-executions/", self.payload(), format="json")
        execution = CommandExecution.objects.get(pk=created.data["id"])
        CommandExecutionOutput.objects.create(execution=execution, stream="stdout", sequence=1, content="ok\n")

        detail = self.client.get(f"/api/command-executions/{execution.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["outputs"][0]["content"], "ok\n")
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get(f"/api/command-executions/{execution.id}/").status_code, 404)
        self.assertEqual(self.client.get("/api/command-executions/").data["count"], 0)

        admin = get_user_model().objects.create_superuser("root-command", password="secret")
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get(f"/api/command-executions/{execution.id}/").status_code, 200)

    @patch("dashboard.command_views.start_execution")
    def test_user_concurrency_limit(self, start):
        for _ in range(2):
            response = self.client.post("/api/command-executions/", self.payload(), format="json")
            self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.post("/api/command-executions/", self.payload(), format="json").status_code, 409)

    def test_stop_marks_active_task_and_rejects_finished_task(self):
        execution = CommandExecution.objects.create(
            operator=self.user, operator_name="executor", operator_username="executor",
            file_config=self.config, project_name="demo", host_name="node-01", ip_address="192.0.2.20",
            mode="shell", working_directory="/root", command="sleep 60",
        )
        response = self.client.post(f"/api/command-executions/{execution.id}/stop/")
        self.assertEqual(response.status_code, 200)
        execution.refresh_from_db()
        self.assertTrue(execution.stop_requested)
        execution.status = "succeeded"
        execution.save(update_fields=["status"])
        self.assertEqual(self.client.post(f"/api/command-executions/{execution.id}/stop/").status_code, 409)

    def test_options_include_machine_and_remote_files(self):
        response = self.client.get("/api/command-executions/options/")
        self.assertEqual(response.status_code, 200)
        machine = next(item for item in response.data["machines"] if item["id"] == self.config.id)
        self.assertEqual(machine["files"][0]["path"], "/srv/manifests/k8s/app.yaml")


class CommandExecutionRunnerTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("runner")
        self.account = Account.objects.create(name="SSH", username="root")
        self.config = FileConfig.objects.create(project="demo", host_name="node", ip_address="192.0.2.30", account=self.account)
        self.execution = CommandExecution.objects.create(
            operator=self.user, operator_name="runner", operator_username="runner", file_config=self.config,
            project_name="demo", host_name="node", ip_address="192.0.2.30", mode="shell",
            working_directory="/root", command="printf ok", requested_ip="198.51.100.1",
        )

    @patch("dashboard.command_execution._broadcast")
    @patch("dashboard.command_execution.connect")
    def test_runner_persists_stdout_stderr_exit_code_and_final_audit(self, connect, broadcast):
        from .command_execution import _run_execution
        channel = MagicMock()
        channel.recv_ready.side_effect = [True, False, False]
        channel.recv.side_effect = [b"ok\n"]
        channel.recv_stderr_ready.side_effect = [True, False, False]
        channel.recv_stderr.side_effect = [b"warn\n"]
        channel.exit_status_ready.side_effect = [False, True]
        channel.recv_exit_status.return_value = 0
        transport = connect.return_value.get_transport.return_value
        transport.open_session.return_value = channel

        _run_execution(self.execution.id)
        self.execution.refresh_from_db()
        self.assertEqual((self.execution.status, self.execution.exit_code), ("succeeded", 0))
        self.assertEqual(list(self.execution.outputs.values_list("stream", "content")), [("stdout", "ok\n"), ("stderr", "warn\n")])
        self.assertTrue(OperationAudit.objects.filter(module="命令执行", action="成功").exists())
        channel.exec_command.assert_called_once_with("cd -- /root && printf ok")

    @patch("dashboard.command_execution._broadcast")
    @patch("dashboard.command_execution.connect", side_effect=ConnectionError("SSH failed"))
    def test_connection_failure_marks_task_failed(self, connect, broadcast):
        from .command_execution import _run_execution
        _run_execution(self.execution.id)
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, "failed")
        self.assertIn("SSH failed", self.execution.error_message)

    @patch("dashboard.command_execution._broadcast")
    @patch("dashboard.command_execution.connect")
    @patch("dashboard.command_execution.EXECUTION_TIMEOUT_SECONDS", 0)
    def test_timeout_closes_channel_and_marks_task(self, connect, broadcast):
        from .command_execution import _run_execution
        channel = connect.return_value.get_transport.return_value.open_session.return_value
        _run_execution(self.execution.id)
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, "timeout")
        channel.close.assert_called()

    @patch("dashboard.command_execution.connect")
    def test_stop_before_start_never_connects(self, connect):
        from .command_execution import _run_execution
        self.execution.stop_requested = True
        self.execution.save(update_fields=["stop_requested"])
        _run_execution(self.execution.id)
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, "stopped")
        connect.assert_not_called()


class CommandExecutionWebSocketTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = get_user_model().objects.create_user("socket-user")
        role = Role.objects.create(name="终端查看", code="socket_viewer", permissions=["command_execution.view"])
        self.user.roles.add(role)
        self.token = Token.objects.create(user=self.user)
        account = Account.objects.create(name="SSH", username="root")
        config = FileConfig.objects.create(project="demo", host_name="node", ip_address="192.0.2.40", account=account)
        self.execution = CommandExecution.objects.create(
            operator=self.user, operator_name="socket-user", operator_username="socket-user",
            file_config=config, project_name="demo", host_name="node", ip_address="192.0.2.40",
            mode="shell", working_directory="/root", command="pwd", status="succeeded", exit_code=0,
        )
        CommandExecutionOutput.objects.create(execution=self.execution, stream="stdout", sequence=1, content="/root\n")

    async def communicate(self, path):
        from configHub.asgi import application
        communicator = WebsocketCommunicator(application, path, headers=[(b"origin", b"http://localhost:5173")])
        connected, code = await communicator.connect()
        if connected:
            message = await communicator.receive_json_from()
            await communicator.disconnect()
            return connected, message
        return connected, code

    def test_valid_token_receives_persisted_snapshot(self):
        connected, message = async_to_sync(self.communicate)(
            f"/ws/command-executions/{self.execution.id}/?token={self.token.key}",
        )
        self.assertTrue(connected)
        self.assertEqual(message["type"], "snapshot")
        self.assertEqual(message["execution"]["outputs"][0]["content"], "/root\n")

    def test_missing_token_is_rejected(self):
        connected, code = async_to_sync(self.communicate)(f"/ws/command-executions/{self.execution.id}/")
        self.assertFalse(connected)
        self.assertEqual(code, 4403)
