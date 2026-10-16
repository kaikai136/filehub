from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import stat

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Account, FileConfig, RemoteFile, Role
from .security import decrypt_value, encrypt_value
from . import ssh


class FileConfigActionTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="tester")
        user.roles.add(Role.objects.get(code='administrator'))
        self.client.force_authenticate(user)
        self.account = Account.objects.create(name="SSH", username="root")
        self.config = FileConfig.objects.create(
            project="demo", host_name="host", ip_address="192.0.2.1",
            machine_name="machine", file_path="/srv/config", account=self.account,
        )
        self.url = f"/api/file-configs/{self.config.pk}/"

    def snapshot(self):
        self.config.fetch_status = "success"
        self.config.last_fetched_at = timezone.now()
        self.config.save()
        return RemoteFile.objects.create(
            file_config=self.config, project="demo", name="old.conf", relative_path="old.conf",
        )

    @patch("dashboard.ssh.connect")
    def test_ssh_test_never_accesses_sftp_or_the_configured_path(self, connect):
        self.config.file_path = "/missing/path"
        self.config.save()
        response = self.client.post(self.url + "test-connection/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["config"]["connection_status"], "success")
        self.assertEqual(response.data["config"]["fetch_status"], "pending")
        self.assertIsNone(response.data["config"]["last_fetched_at"])
        connect.return_value.open_sftp.assert_not_called()
        connect.return_value.exec_command.assert_not_called()
        connect.return_value.close.assert_called_once()

    @patch("dashboard.views.test_connection")
    def test_failed_ssh_test_preserves_file_snapshot(self, test_connection):
        old = self.snapshot()
        test_connection.side_effect = ConnectionError("登录失败")
        response = self.client.post(self.url + "test-connection/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["config"]["connection_status"], "error")
        self.assertEqual(response.data["config"]["fetch_status"], "success")
        self.assertEqual(response.data["config"]["file_count"], 1)
        self.assertTrue(RemoteFile.objects.filter(pk=old.pk).exists())

    @patch("dashboard.views.test_connection")
    def test_successful_ssh_test_does_not_clear_fetch_failure(self, test_connection):
        self.config.fetch_status = "error"
        self.config.fetch_error = "路径无权限"
        self.config.save()
        response = self.client.post(self.url + "test-connection/")
        self.assertEqual(response.data["config"]["connection_status"], "success")
        self.assertEqual(response.data["config"]["fetch_status"], "error")
        self.assertEqual(response.data["config"]["fetch_error"], "路径无权限")

    @patch("dashboard.views.connect")
    def test_fetch_path_failure_preserves_verified_ssh_and_old_snapshot(self, connect):
        old = self.snapshot()
        fetched_at = self.config.last_fetched_at
        connect.return_value.open_sftp.return_value.stat.side_effect = PermissionError("路径无权限")
        response = self.client.post(self.url + "refresh/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["config"]["connection_status"], "success")
        self.assertEqual(response.data["config"]["fetch_status"], "error")
        self.assertEqual(response.data["config"]["fetch_error"], "路径无权限")
        self.assertEqual(response.data["config"]["file_count"], 1)
        self.config.refresh_from_db()
        self.assertEqual(self.config.last_fetched_at, fetched_at)
        self.assertTrue(RemoteFile.objects.filter(pk=old.pk).exists())
        connect.return_value.close.assert_called_once()

    @patch("dashboard.views.connect", side_effect=ConnectionError("账号认证失败"))
    def test_fetch_login_failure_updates_both_results(self, connect):
        self.snapshot()
        response = self.client.post(self.url + "refresh/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["config"]["connection_status"], "error")
        self.assertEqual(response.data["config"]["fetch_status"], "error")
        self.assertEqual(response.data["config"]["file_count"], 1)

    @patch("dashboard.views.list_remote_files", return_value=[])
    @patch("dashboard.views.connect")
    def test_empty_directory_is_a_successful_zero_file_snapshot(self, connect, list_files):
        self.snapshot()
        response = self.client.post(self.url + "refresh/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["config"]["connection_status"], "success")
        self.assertEqual(response.data["config"]["fetch_status"], "success")
        self.assertEqual(response.data["file_count"], 0)
        self.assertEqual(response.data["config"]["file_count"], 0)
        self.assertFalse(self.config.remote_files.exists())
        self.assertIsNotNone(response.data["config"]["last_fetched_at"])
        listing = self.client.get("/api/file-configs/").data[0]
        self.assertEqual(listing["fetch_status"], "success")
        self.assertEqual(listing["file_count"], 0)

    @patch("dashboard.views.list_remote_files")
    @patch("dashboard.views.connect")
    def test_directory_snapshot_includes_empty_folders_without_counting_them(self, connect, list_files):
        listing = ssh.RemoteListing()
        listing.directory_paths = ["empty", ".git", ".git/objects"]
        listing.append({"project": "demo", "name": "HEAD", "relative_path": ".git/HEAD"})
        list_files.return_value = listing
        response = self.client.post(self.url + "refresh/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["file_count"], 1)
        self.assertEqual(response.data["config"]["directory_paths"], [".git", ".git/objects", "empty"])
        self.assertEqual(self.client.get("/api/file-configs/").data[0]["directory_paths"], [".git", ".git/objects", "empty"])
        self.assertEqual(len(self.client.get("/api/file-lists/").data), 1)
        changed = self.client.patch(self.url, {"file_path": "/new"})
        self.assertEqual(changed.data["directory_paths"], [])

    @patch("dashboard.views.list_remote_files")
    @patch("dashboard.views.connect")
    def test_successful_refresh_replaces_files_and_persists_count(self, connect, list_files):
        self.snapshot()
        list_files.return_value = [
            {"project": "demo", "name": name, "relative_path": path}
            for name, path in [("a.conf", "a.conf"), ("b.conf", "sub/b.conf")]
        ]
        response = self.client.post(self.url + "refresh/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["file_count"], 2)
        self.assertEqual(self.client.get("/api/file-configs/").data[0]["file_count"], 2)
        self.assertEqual(len(self.client.get("/api/file-lists/").data), 2)
        self.assertFalse(self.config.remote_files.filter(name="old.conf").exists())

    @patch("dashboard.models.RemoteFile.objects.bulk_create", side_effect=IntegrityError("保存失败"))
    @patch("dashboard.views.list_remote_files", return_value=[])
    @patch("dashboard.views.connect")
    def test_snapshot_replacement_rolls_back_on_database_failure(self, connect, list_files, bulk_create):
        old = self.snapshot()
        response = self.client.post(self.url + "refresh/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["config"]["fetch_status"], "error")
        self.assertTrue(RemoteFile.objects.filter(pk=old.pk).exists())

    def test_path_change_invalidates_only_file_results(self):
        self.snapshot()
        self.config.connection_status = "success"
        self.config.save()
        response = self.client.patch(self.url, {"file_path": "/srv/new"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["connection_status"], "success")
        self.assertEqual(response.data["fetch_status"], "pending")
        self.assertEqual(response.data["file_count"], 0)
        self.assertIsNone(response.data["last_fetched_at"])

    def test_host_change_invalidates_both_results(self):
        self.snapshot()
        self.config.connection_status = "success"
        self.config.save()
        response = self.client.patch(self.url, {"ip_address": "192.0.2.2"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["connection_status"], "pending")
        self.assertEqual(response.data["fetch_status"], "pending")
        self.assertEqual(response.data["file_count"], 0)

    def second_machine(self):
        other = FileConfig.objects.create(
            project="other", host_name="other", ip_address="192.0.2.2",
            machine_name="other", file_path="/srv/other", account=self.account,
            connection_status="success", fetch_status="success",
            last_verified_at=timezone.now(), last_fetched_at=timezone.now(),
        )
        RemoteFile.objects.create(file_config=other, project="other", name="other.conf", relative_path="other.conf")
        return other

    def test_account_template_edit_preserves_each_machine_credentials_and_results(self):
        self.snapshot()
        self.config.connection_status = "success"
        self.config.save()
        other = self.second_machine()
        before = list(FileConfig.objects.values())
        response = self.client.patch(f"/api/accounts/{self.account.pk}/", {
            "username": "another-user", "password": "new-password", "private_key": "new-key", "is_active": False,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(FileConfig.objects.values()), before)
        self.assertEqual(self.config.remote_files.count(), 1)
        self.assertEqual(other.remote_files.count(), 1)

    def test_reselecting_updated_account_only_updates_current_machine(self):
        self.snapshot()
        other = self.second_machine()
        other_before = FileConfig.objects.filter(pk=other.pk).values().get()
        files_before = list(other.remote_files.values())
        self.client.patch(f"/api/accounts/{self.account.pk}/", {"username": "new-user", "password": "new-password"})
        response = self.client.patch(self.url, {"account_id": self.account.pk})
        self.assertEqual(response.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.ssh_account.username, "new-user")
        self.assertEqual(decrypt_value(self.config.ssh_account.encrypted_password), "new-password")
        self.assertEqual(self.config.connection_status, "pending")
        self.assertEqual(self.config.fetch_status, "pending")
        self.assertFalse(self.config.remote_files.exists())
        self.assertEqual(FileConfig.objects.filter(pk=other.pk).values().get(), other_before)
        self.assertEqual(list(other.remote_files.values()), files_before)
        self.assertNotIn("account_snapshot", response.data)
        self.assertNotIn("encrypted_password", str(response.data))

    def test_switching_account_and_path_does_not_change_other_record(self):
        other = self.second_machine()
        before = FileConfig.objects.filter(pk=other.pk).values().get()
        files_before = list(other.remote_files.values())
        account = Account.objects.create(name="separate", username="user", encrypted_password=encrypt_value("secret"))
        response = self.client.patch(self.url, {"account_id": account.pk, "file_path": "/new/path"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["account_id"], account.pk)
        self.assertEqual(FileConfig.objects.filter(pk=other.pk).values().get(), before)
        self.assertEqual(list(other.remote_files.values()), files_before)

    @patch("dashboard.ssh.paramiko.SSHClient")
    def test_ssh_login_uses_machine_credentials_after_template_edit(self, ssh_client):
        self.account.encrypted_password = encrypt_value("original-password")
        self.account.save()
        self.config.bind_account(self.account)
        self.config.save()
        self.client.patch(f"/api/accounts/{self.account.pk}/", {"username": "changed", "password": "changed"})
        response = self.client.post(self.url + "test-connection/")
        self.assertEqual(response.status_code, 200)
        kwargs = ssh_client.return_value.connect.call_args.kwargs
        self.assertEqual(kwargs["username"], "root")
        self.assertEqual(kwargs["password"], "original-password")

    @patch("dashboard.views.list_remote_files", return_value=[])
    @patch("dashboard.views.connect")
    def test_remote_actions_never_change_other_machine(self, connect, list_files):
        other = self.second_machine()
        before = FileConfig.objects.filter(pk=other.pk).values().get()
        files_before = list(other.remote_files.values())
        self.assertEqual(self.client.post(self.url + "refresh/").status_code, 200)
        self.assertEqual(FileConfig.objects.filter(pk=other.pk).values().get(), before)
        self.assertEqual(list(other.remote_files.values()), files_before)

    @patch("dashboard.views.test_connection")
    def test_old_login_result_cannot_overwrite_edited_machine(self, test_connection):
        test_connection.side_effect = lambda config: self.client.patch(self.url, {"ip_address": "192.0.2.3"})
        response = self.client.post(self.url + "test-connection/")
        self.assertEqual(response.status_code, 409)
        self.config.refresh_from_db()
        self.assertEqual(self.config.ip_address, "192.0.2.3")
        self.assertEqual(self.config.connection_status, "pending")
        self.assertEqual(response.data["config"]["ip_address"], "192.0.2.3")

    @patch("dashboard.views.test_connection")
    def test_old_login_failure_cannot_overwrite_new_account(self, test_connection):
        def fail_after_edit(config):
            self.client.patch(self.url, {"ip_address": "192.0.2.3"})
            raise ConnectionError("old credentials failed")
        test_connection.side_effect = fail_after_edit
        response = self.client.post(self.url + "test-connection/")
        self.assertEqual(response.status_code, 409)
        self.config.refresh_from_db()
        self.assertEqual(self.config.connection_status, "pending")
        self.assertEqual(self.config.connection_error, "")

    @patch("dashboard.views.list_remote_files")
    @patch("dashboard.views.connect")
    def test_old_file_result_is_discarded_after_path_edit(self, connect, list_files):
        def list_after_edit(config, client):
            self.client.patch(self.url, {"file_path": "/new/path"})
            return [{"project": "demo", "name": "stale.conf", "relative_path": "stale.conf"}]
        list_files.side_effect = list_after_edit
        response = self.client.post(self.url + "refresh/")
        self.assertEqual(response.status_code, 409)
        self.config.refresh_from_db()
        self.assertEqual(self.config.file_path, "/new/path")
        self.assertEqual(self.config.fetch_status, "pending")
        self.assertFalse(self.config.remote_files.exists())

    def test_stale_editor_is_rejected(self):
        old_revision = self.config.revision
        self.client.patch(self.url, {"machine_name": "new name"})
        response = self.client.patch(self.url, {"revision": old_revision, "account_id": self.account.pk})
        self.assertEqual(response.status_code, 409)
        self.config.refresh_from_db()
        self.assertEqual(self.config.machine_name, "new name")

    @patch("dashboard.views.read_remote_file", return_value="server:\n  port: 8080\n")
    def test_file_content_can_be_opened(self, read_remote_file):
        remote_file = self.snapshot()
        response = self.client.get(f"/api/file-lists/{remote_file.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["content"], "server:\n  port: 8080\n")
        self.assertEqual(response.data["encoding"], "utf-8")
        read_remote_file.assert_called_once()

    @patch("dashboard.views.write_remote_file")
    def test_file_content_can_be_saved(self, write_remote_file):
        remote_file = self.snapshot()
        write_remote_file.return_value = SimpleNamespace(st_size=18, st_mtime=1_700_000_000)
        response = self.client.patch(f"/api/file-lists/{remote_file.pk}/", {"content": "server:\n  port: 80\n"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["file"]["size"], 18)
        remote_file.refresh_from_db()
        self.assertEqual(remote_file.size, 18)
        write_remote_file.assert_called_once()


class SSHTests(SimpleTestCase):
    def entry(self, name, directory=False):
        return SimpleNamespace(
            filename=name, st_mode=stat.S_IFDIR if directory else stat.S_IFREG,
            st_size=10, st_mtime=0,
        )

    def config(self):
        return SimpleNamespace(
            project="demo", file_path="/srv/config", ip_address="192.0.2.1", port=22,
            ssh_account=SimpleNamespace(
                username="root", is_active=True, encrypted_private_key="",
                encrypted_password=encrypt_value("test-only"),
            ),
        )

    def test_recursive_listing_uses_remote_paths_and_excludes_directories(self):
        client = MagicMock()
        sftp = client.open_sftp.return_value
        sftp.stat.return_value = self.entry("config", directory=True)
        tree = {
            "/srv/config": [self.entry("a.conf"), self.entry("sub", directory=True), self.entry("empty", directory=True)],
            "/srv/config/sub": [self.entry("b.conf")],
            "/srv/config/empty": [],
        }
        sftp.listdir_attr.side_effect = lambda path: tree[path]
        files = ssh.list_remote_files(self.config(), client=client)
        self.assertEqual([item["relative_path"] for item in files], ["a.conf", "sub/b.conf"])
        self.assertEqual([item["file_type"] for item in files], ["file", "file"])
        self.assertEqual(files.directory_paths, ["sub", "empty"])
        client.close.assert_called_once()
        sftp.close.assert_called_once()

    def test_sftp_open_failure_still_closes_ssh(self):
        client = MagicMock()
        client.open_sftp.side_effect = PermissionError("SFTP 不可用")
        with self.assertRaises(PermissionError):
            ssh.list_remote_files(self.config(), client=client)
        client.close.assert_called_once()

    def test_listing_includes_hidden_files_and_recurses_into_hidden_directories(self):
        client = MagicMock()
        sftp = client.open_sftp.return_value
        sftp.stat.return_value = self.entry("config", directory=True)
        tree = {
            "/srv/config": [
                self.entry("a.yaml"), self.entry(".env"),
                self.entry(".git", directory=True), self.entry("sub", directory=True),
            ],
            "/srv/config/sub": [
                self.entry("b.yaml"), self.entry(".backup", directory=True), self.entry(".secret"),
            ],
            "/srv/config/sub/.backup": [self.entry("old.yaml")],
            "/srv/config/.git": [self.entry("HEAD"), self.entry("objects", directory=True)],
            "/srv/config/.git/objects": [self.entry("object")],
        }
        sftp.listdir_attr.side_effect = lambda path: tree[path]
        files = ssh.list_remote_files(self.config(), client=client)
        self.assertCountEqual([item["relative_path"] for item in files], [
            "a.yaml", ".env", "sub/b.yaml", "sub/.secret", "sub/.backup/old.yaml",
            ".git/HEAD", ".git/objects/object",
        ])
        self.assertEqual(sftp.listdir_attr.call_count, 5)

    def test_explicit_hidden_root_is_still_listed(self):
        config = self.config()
        config.file_path = "/root/.kube/.k8s_yaml"
        client = MagicMock()
        sftp = client.open_sftp.return_value
        sftp.stat.return_value = self.entry(".k8s_yaml", directory=True)
        sftp.listdir_attr.return_value = [self.entry("app.yaml"), self.entry(".env")]
        files = ssh.list_remote_files(config, client=client)
        self.assertEqual([item["relative_path"] for item in files], ["app.yaml", ".env"])
        sftp.listdir_attr.assert_called_once_with(config.file_path)

    def test_single_file_path_returns_one_file(self):
        client = MagicMock()
        client.open_sftp.return_value.stat.return_value = self.entry("config")
        files = ssh.list_remote_files(self.config(), client=client)
        self.assertEqual(len(files), 1)
        client.open_sftp.return_value.listdir_attr.assert_not_called()

    def test_remote_text_file_can_be_read_as_utf8(self):
        client = MagicMock()
        sftp = client.open_sftp.return_value
        sftp.stat.return_value = self.entry("app.yaml")
        sftp.file.return_value.__enter__.return_value.read.return_value = "名称: 示例\n".encode()
        remote_file = SimpleNamespace(file_config=self.config(), relative_path="app.yaml")
        self.assertEqual(ssh.read_remote_file(remote_file, client=client), "名称: 示例\n")
        sftp.file.assert_called_once_with("/srv/config/app.yaml", "rb")
        client.close.assert_called_once()

    def test_remote_text_file_is_saved_with_atomic_rename(self):
        client = MagicMock()
        sftp = client.open_sftp.return_value
        original = self.entry("app.yaml")
        original.st_mode = stat.S_IFREG | 0o640
        updated = self.entry("app.yaml")
        updated.st_size = 12
        sftp.stat.side_effect = [original, updated]
        remote_file = SimpleNamespace(file_config=self.config(), relative_path="app.yaml")
        attrs = ssh.write_remote_file(remote_file, "name: demo\n", client=client)
        self.assertEqual(attrs.st_size, 12)
        handle = sftp.file.return_value.__enter__.return_value
        handle.write.assert_called_once_with(b"name: demo\n")
        sftp.chmod.assert_called_once()
        sftp.posix_rename.assert_called_once()
        client.close.assert_called_once()

    @patch("dashboard.ssh.paramiko.SSHClient")
    def test_unauthenticated_transport_is_not_a_success(self, ssh_client):
        ssh_client.return_value.get_transport.return_value.is_authenticated.return_value = False
        with self.assertRaises(ConnectionError):
            ssh.connect(self.config())
        ssh_client.return_value.close.assert_called_once()

    @patch("dashboard.ssh.paramiko.SSHClient")
    def test_disabled_account_does_not_attempt_login(self, ssh_client):
        config = self.config()
        config.ssh_account.is_active = False
        with self.assertRaisesMessage(ValueError, "关联账号已禁用"):
            ssh.connect(config)
        ssh_client.assert_not_called()
