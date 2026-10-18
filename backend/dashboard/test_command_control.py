from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .command_policy import active_rules, default_rules
from .models import CommandPolicy, OperationAudit, Role, Account, FileConfig
from .shell_safety import BLOCKED_COMMANDS, shell_command_error


class CommandControlTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("policy-admin", password="secret")
        self.client.force_authenticate(self.admin)

    def test_defaults_include_every_builtin_and_family_rule(self):
        response = self.client.get("/api/command-control/")
        self.assertEqual(response.status_code, 200)
        rules = response.data["rules"]
        self.assertTrue(set(BLOCKED_COMMANDS).issubset({rule["command"] for rule in rules}))
        for command in ["rm x", "mkfs.ext4 x", "fsck.ext4 x", "python3.13 x"]:
            self.assertIsNotNone(shell_command_error(command, rules))
        self.assertEqual(CommandPolicy.objects.count(), 1)

    def test_save_disable_add_restore_and_stale_revision(self):
        policy = self.client.get("/api/command-control/").data
        rules = policy["rules"]
        next(rule for rule in rules if rule["command"] == "rm")["enabled"] = False
        rules.append({"command": "custom-danger", "category": "自定义", "match": "exact", "enabled": True})
        response = self.client.patch("/api/command-control/", {"rules": rules, "revision": policy["revision"]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(shell_command_error("rm /tmp/x", active_rules()))
        self.assertIsNotNone(shell_command_error("custom-danger", active_rules()))
        self.assertIsNotNone(shell_command_error("echo x > /tmp/x", active_rules()))
        self.assertTrue(OperationAudit.objects.filter(module="命令控制", action="修改").exists())
        stale = self.client.patch("/api/command-control/", {"rules": [], "revision": policy["revision"]}, format="json")
        self.assertEqual(stale.status_code, 409)
        restored = self.client.patch("/api/command-control/", {"rules": default_rules(), "revision": response.data["revision"]}, format="json")
        self.assertEqual(restored.status_code, 200)
        self.assertIsNotNone(shell_command_error("rm /tmp/x", active_rules()))

    def test_only_superuser_can_edit_and_view_permission_is_required(self):
        user = get_user_model().objects.create_user("policy-viewer")
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get("/api/command-control/").status_code, 403)
        role = Role.objects.create(name="命令控制查看", code="policy_viewer", permissions=["command_control.view"])
        user.roles.add(role)
        response = self.client.get("/api/command-control/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["can_edit"])
        self.assertEqual(self.client.patch("/api/command-control/", {"rules": [], "revision": 1}, format="json").status_code, 403)

    def test_rejects_invalid_rules_without_mutating_policy(self):
        self.client.get("/api/command-control/")
        valid = {"command": "rm", "category": "删除", "match": "exact", "enabled": True}
        for rules in [None, {}, [valid, valid], [{**valid, "command": "/bin/rm"}], [{**valid, "command": "rm -rf"}], [{**valid, "enabled": 1}], [{**valid, "match": "regex"}], [{**valid, "match": "python_version"}], [{**valid, "category": ""}]]:
            with self.subTest(rules=rules):
                response = self.client.patch("/api/command-control/", {"rules": rules, "revision": 1}, format="json")
                self.assertEqual(response.status_code, 400)
        self.assertEqual(CommandPolicy.objects.get(pk=1).revision, 1)

    @patch("dashboard.command_execution._broadcast")
    @patch("dashboard.command_execution.connect")
    def test_runner_reads_current_saved_rules_before_connecting(self, connect, broadcast):
        from .command_execution import _run_execution
        from .models import CommandExecution
        policy = self.client.get("/api/command-control/").data
        policy["rules"].append({"command": "whoami", "category": "新规则", "match": "exact", "enabled": True})
        account = Account.objects.create(name="SSH queued", username="root")
        config = FileConfig.objects.create(project="queued", host_name="node", ip_address="192.0.2.51", account=account)
        execution = CommandExecution.objects.create(operator=self.admin, file_config=config, mode="shell", command="whoami", working_directory="/root", host_name="node", ip_address="192.0.2.51")
        self.assertEqual(self.client.patch("/api/command-control/", {"rules": policy["rules"], "revision": policy["revision"]}, format="json").status_code, 200)
        _run_execution(execution.id)
        execution.refresh_from_db()
        self.assertEqual(execution.status, "failed")
        self.assertIn("whoami", execution.error_message)
        connect.assert_not_called()

    @patch("dashboard.command_views.start_execution")
    def test_saved_custom_rule_is_enforced_on_submission(self, start):
        policy = self.client.get("/api/command-control/").data
        policy["rules"].append({"command": "whoami", "category": "测试规则", "match": "exact", "enabled": True})
        self.assertEqual(self.client.patch("/api/command-control/", {"rules": policy["rules"], "revision": policy["revision"]}, format="json").status_code, 200)
        account = Account.objects.create(name="SSH policy", username="root")
        config = FileConfig.objects.create(project="policy", host_name="node", ip_address="192.0.2.50", account=account)
        response = self.client.post("/api/command-executions/", {"mode": "shell", "file_config_id": config.id, "command": "whoami"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "dangerous_shell_command")
        start.assert_not_called()
