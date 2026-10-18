from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import FileAudit, OperationAudit, Role, SystemSetting


User = get_user_model()


class SystemSettingsTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("settings-admin", password="secret123", first_name="管理员")
        self.client.force_authenticate(self.admin)

    def test_get_creates_defaults_and_returns_current_user(self):
        response = self.client.get("/api/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["settings"]["font_size"], 16)
        self.assertEqual(response.data["settings"]["github_url"], "https://github.com/")
        self.assertTrue(response.data["settings"]["can_edit_global"])
        self.assertEqual(response.data["user"]["username"], "settings-admin")
        self.assertTrue(SystemSetting.objects.filter(pk=1).exists())

    def test_superuser_can_save_global_and_profile_settings(self):
        response = self.client.patch("/api/settings/", {
            "settings": {
                "font_size": 18, "watermark_enabled": True, "watermark_mode": "custom", "watermark_text": "内部环境",
                "watermark_opacity": 20, "watermark_rotation": -15,
                "file_audit_retention_days": 365, "operation_audit_retention_days": 90,
                "github_url": "https://github.com/example/filehub",
            },
            "user": {"username": "settings-admin", "name": "系统管理员", "email": "admin@example.com"},
        }, format="json")

        self.assertEqual(response.status_code, 200)
        setting = SystemSetting.objects.get(pk=1)
        self.assertEqual((setting.font_size, setting.watermark_mode, setting.watermark_text, setting.file_audit_retention_days), (18, "custom", "内部环境", 365))
        self.assertEqual(setting.github_url, "https://github.com/example/filehub")
        self.admin.refresh_from_db()
        self.assertEqual((self.admin.first_name, self.admin.email), ("系统管理员", "admin@example.com"))

    def test_password_change_requires_current_password(self):
        response = self.client.patch("/api/settings/", {
            "user": {"username": "settings-admin", "name": "管理员", "email": "", "current_password": "wrong", "new_password": "newsecret"},
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("当前密码", response.data["detail"])

    def test_non_superuser_can_edit_profile_but_not_global_settings(self):
        role = Role.objects.create(name="设置查看", code="settings_viewer", permissions=["settings.view"])
        user = User.objects.create_user("settings-user", password="secret123", first_name="用户")
        user.roles.add(role)
        self.client.force_authenticate(user)
        profile = self.client.patch("/api/settings/", {"user": {"username": "settings-user", "name": "新姓名", "email": "user@example.com"}}, format="json")
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["user"]["name"], "新姓名")

        denied = self.client.patch("/api/settings/", {"settings": {"font_size": 18}}, format="json")
        self.assertEqual(denied.status_code, 403)

    def test_appearance_is_available_to_authenticated_user_without_settings_permission(self):
        user = User.objects.create_user("appearance-user")
        self.client.force_authenticate(user)

        response = self.client.get("/api/appearance/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("file_audit_retention_days", response.data)
        self.assertEqual(response.data["watermark_mode"], "username")
        self.assertEqual(response.data["watermark_content"], "appearance-user")
        self.assertEqual(response.data["github_url"], "https://github.com/")

    def test_github_url_requires_http_or_https(self):
        for value in ["", "javascript:alert(1)", "ftp://github.com/example/filehub", "github.com/example/filehub"]:
            response = self.client.patch("/api/settings/", {"settings": {"github_url": value}}, format="json")
            self.assertEqual(response.status_code, 400)

    def test_custom_watermark_requires_text(self):
        response = self.client.patch("/api/settings/", {
            "settings": {"watermark_mode": "custom", "watermark_text": ""},
            "user": {"username": self.admin.username, "name": "管理员", "email": ""},
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("不能为空", response.data["detail"])

    def test_saving_retention_policy_purges_expired_records(self):
        old_file = FileAudit.objects.create(project_name="old", ip_address="192.0.2.1", directory="/old", relative_path="old", diff="-a\n+b\n")
        old_operation = OperationAudit.objects.create(module="测试", action="编辑")
        expired_at = timezone.now() - timedelta(days=31)
        FileAudit.objects.filter(pk=old_file.pk).update(changed_at=expired_at)
        OperationAudit.objects.filter(pk=old_operation.pk).update(occurred_at=expired_at)

        response = self.client.patch("/api/settings/", {
            "settings": {"file_audit_retention_days": 30, "operation_audit_retention_days": 30},
            "user": {"username": self.admin.username, "name": "管理员", "email": ""},
        }, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(FileAudit.objects.filter(pk=old_file.pk).exists())
        self.assertFalse(OperationAudit.objects.filter(pk=old_operation.pk).exists())
