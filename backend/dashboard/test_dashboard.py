from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Account, FileConfig, OperationAudit, Project, RemoteFile, Role


class DashboardTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("dashboard-user")
        self.user.roles.add(Role.objects.get(code="administrator"))
        self.client.force_authenticate(self.user)

    @patch("dashboard.views.collect_system_metrics")
    def test_dashboard_returns_collected_metrics_and_real_resource_counts(self, collect):
        collect.return_value = {
            "sampled_at": "2026-01-01T00:00:00Z",
            "server": {"name": "real-host", "address": "192.0.2.10", "os": "Linux", "uptime": "1 小时", "status": "online"},
            "metrics": [{"key": "cpu", "value": 12.5}],
            "chart": {"labels": ["00:00:00"], "timestamps": ["2026-01-01T00:00:00Z"], "cpu": [12.5], "memory": [30.0]},
        }
        account = Account.objects.create(name="SSH", username="root")
        project = Project.objects.create(name="production")
        config = FileConfig.objects.create(project="production", project_node=project, host_name="web", ip_address="192.0.2.20", account=account)
        RemoteFile.objects.create(file_config=config, project="production", name="app.yml", relative_path="app.yml")

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["server"]["name"], "real-host")
        self.assertEqual([item["count"] for item in response.data["resources"]], [1, 1, 1, 1])
        collect.assert_called_once_with()

    @patch("dashboard.views.collect_system_metrics")
    def test_activity_comes_from_operation_audit(self, collect):
        collect.return_value = {"sampled_at": "now", "server": {}, "metrics": [], "chart": {}}
        OperationAudit.objects.create(
            operator=self.user, operator_name="控制台用户", operator_username=self.user.username,
            module="项目管理", action="新增", object_name="生产环境", detail="创建项目",
        )

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.data["activity"][0]["title"], "项目管理 · 新增")
        self.assertEqual(response.data["activity"][0]["detail"], "创建项目")

    @patch("dashboard.views.collect_system_metrics")
    def test_activity_is_hidden_without_audit_permission(self, collect):
        collect.return_value = {"sampled_at": "now", "server": {}, "metrics": [], "chart": {}}
        viewer = get_user_model().objects.create_user("dashboard-viewer")
        role = Role.objects.create(name="仅概览", code="dashboard_only", permissions=["dashboard.view"])
        viewer.roles.add(role)
        self.client.force_authenticate(viewer)
        OperationAudit.objects.create(module="用户管理", action="删除", detail="敏感详情")

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activity"], [])
        self.assertEqual(response.data["resources"], [])
