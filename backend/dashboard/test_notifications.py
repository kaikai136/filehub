from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Account, ConfigNotification, ConfigNotificationRead, FileConfig, Role
from .notifications import record_config_notification


class ConfigNotificationTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.operator = User.objects.create_user("operator", password="secret", first_name="张三")
        self.operator.roles.add(Role.objects.get(code="administrator"))
        self.viewer = User.objects.create_user("viewer", password="secret")
        self.viewer.roles.add(Role.objects.get(code="viewer"))
        self.roleless = User.objects.create_user("roleless", password="secret")
        self.account = Account.objects.create(name="SSH", username="root")
        self.config = FileConfig.objects.create(
            project="demo", host_name="web-01", ip_address="192.0.2.10",
            file_path="/etc/nginx", account=self.account,
        )
        self.client.force_authenticate(self.operator)

    def create_notification(self, event_type="updated", config=None):
        return record_config_notification(
            type("Request", (), {"user": self.operator})(), event_type, config=config or self.config,
        )

    def test_create_edit_delete_generate_snapshot_notifications(self):
        created = self.client.post("/api/file-configs/", {
            "source_config_id": self.config.id,
            "source_revision": self.config.revision,
            "project_id": self.config.project_node_id,
            "file_path": "/etc/app",
        }, format="json")
        self.assertEqual(created.status_code, 201)
        config_id = created.data["id"]

        updated = self.client.patch(f"/api/file-configs/{config_id}/", {
            "file_path": "/etc/app-v2", "revision": created.data["revision"],
        }, format="json")
        self.assertEqual(updated.status_code, 200)
        deleted = self.client.delete(
            f"/api/file-configs/{config_id}/", {"revision": updated.data["revision"]}, format="json",
        )
        self.assertEqual(deleted.status_code, 204)

        notifications = list(ConfigNotification.objects.filter(file_config_id_snapshot=config_id).order_by("created_at"))
        self.assertEqual([item.event_type for item in notifications], ["created", "updated", "deleted"])
        self.assertEqual(notifications[1].previous_path, "/etc/app")
        self.assertEqual(notifications[1].path, "/etc/app-v2")
        self.assertEqual(notifications[2].path, "/etc/app-v2")
        self.assertIsNone(notifications[2].file_config_id)
        self.assertEqual(notifications[2].host_name, "web-01")
        self.assertEqual(notifications[2].ip_address, "192.0.2.10")

    def test_failed_config_request_does_not_create_notification(self):
        response = self.client.post("/api/file-configs/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ConfigNotification.objects.exists())

    @patch("dashboard.notifications.ConfigNotification.objects.create", side_effect=RuntimeError("notification unavailable"))
    def test_notification_failure_does_not_change_successful_business_response(self, create):
        response = self.client.patch(
            f"/api/file-configs/{self.config.id}/", {"file_path": "/srv/new", "revision": self.config.revision}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.file_path, "/srv/new")
        create.assert_called_once()

    def test_list_returns_latest_twenty_and_expected_message(self):
        for index in range(25):
            ConfigNotification.objects.create(
                event_type="updated", operator=self.operator, operator_name="张三", operator_username="operator",
                project_name="demo", host_name=f"web-{index:02d}", ip_address="192.0.2.10", path=f"/etc/{index}",
                file_config=self.config, file_config_id_snapshot=self.config.id,
            )
        response = self.client.get("/api/notifications/?limit=20")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 20)
        self.assertEqual(response.data["unread_count"], 25)
        self.assertEqual(response.data["latest"]["id"], response.data["items"][0]["id"])
        self.assertIn("张三", response.data["latest"]["message"])
        self.assertIn("更改了 web-24（192.0.2.10） /etc/24 的配置", response.data["latest"]["message"])

    def test_read_state_is_persisted_per_user(self):
        notification = self.create_notification()
        response = self.client.post(f"/api/notifications/{notification.id}/read/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ConfigNotificationRead.objects.filter(notification=notification, user=self.operator).exists())
        self.assertTrue(self.client.get("/api/notifications/").data["items"][0]["is_read"])

        self.client.force_authenticate(self.viewer)
        viewer_response = self.client.get("/api/notifications/")
        self.assertFalse(viewer_response.data["items"][0]["is_read"])
        self.assertEqual(viewer_response.data["unread_count"], 1)

    def test_mark_all_only_affects_current_user(self):
        first = self.create_notification("created")
        second = self.create_notification("updated")
        self.assertEqual(self.client.post("/api/notifications/read-all/").status_code, 200)
        self.assertEqual(ConfigNotificationRead.objects.filter(user=self.operator).count(), 2)
        self.assertEqual(self.client.get("/api/notifications/").data["unread_count"], 0)

        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get("/api/notifications/").data["unread_count"], 2)
        self.assertFalse(ConfigNotificationRead.objects.filter(user=self.viewer, notification__in=[first, second]).exists())

    def test_permission_is_required_and_superuser_bypasses_roles(self):
        self.client.force_authenticate(self.roleless)
        self.assertEqual(self.client.get("/api/notifications/").status_code, 403)

        superuser = get_user_model().objects.create_superuser("root", password="secret")
        self.client.force_authenticate(superuser)
        self.assertEqual(self.client.get("/api/notifications/").status_code, 200)
