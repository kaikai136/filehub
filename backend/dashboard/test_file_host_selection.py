from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Account, FileConfig, Project, RemoteFile, Role


class FileHostSelectionTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='file-selector')
        user.roles.add(Role.objects.get(code='administrator'))
        self.client.force_authenticate(user)
        self.account = Account.objects.create(name='original', username='original-user')
        self.host = FileConfig.objects.create(
            project='selected', host_name='node', machine_name='remote-host',
            ip_address='192.0.2.1', port=2222, account=self.account,
        )
        self.payload = {
            'project_id': self.host.project_node_id, 'source_config_id': self.host.pk,
            'source_revision': self.host.revision, 'file_path': '/etc/app',
        }

    def test_create_uses_selected_machine_and_its_account_snapshot(self):
        original = FileConfig.objects.values().get(pk=self.host.pk)
        self.account.username = 'changed-template'
        self.account.save()
        response = self.client.post('/api/file-configs/', {
            **self.payload, 'ip_address': '192.0.2.99', 'account_id': 999,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        created = FileConfig.objects.get(pk=response.data['id'])
        self.assertNotEqual(created.pk, self.host.pk)
        self.assertEqual(created.host_config_id, self.host.pk)
        self.assertEqual(created.project_node_id, self.host.project_node_id)
        self.assertEqual((created.ip_address, created.port, created.machine_name), ('192.0.2.1', 2222, 'remote-host'))
        self.assertEqual(created.file_path, '/etc/app')
        self.assertEqual(created.ssh_account.username, 'original-user')
        self.assertEqual(created.account_snapshot, self.host.account_snapshot)
        self.assertEqual(FileConfig.objects.values().get(pk=self.host.pk), original)
        self.assertNotIn('account_snapshot', response.data)
        self.assertEqual(created.fetch_status, 'pending')

    def test_wrong_project_and_stale_selection_do_not_create_config(self):
        other = Project.objects.create(name='other')
        for changes, expected in [
            ({'project_id': other.pk}, 400),
            ({'source_revision': 999}, 409),
            ({'source_config_id': 999}, 400),
            ({'source_config_id': 'invalid'}, 400),
            ({'file_path': '   '}, 400),
            ({'file_path': 'x' * 501}, 400),
        ]:
            with self.subTest(changes=changes):
                response = self.client.post('/api/file-configs/', {**self.payload, **changes}, format='json')
                self.assertEqual(response.status_code, expected)
                self.assertEqual(FileConfig.objects.count(), 1)

    def test_multiple_paths_have_independent_file_caches(self):
        first = self.client.post('/api/file-configs/', self.payload, format='json')
        second = self.client.post('/api/file-configs/', {**self.payload, 'file_path': '/srv/app'}, format='json')
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        cached = RemoteFile.objects.create(file_config_id=first.data['id'], project='selected', name='a', relative_path='a')
        self.assertEqual(self.client.delete(f"/api/file-configs/{second.data['id']}/").status_code, 204)
        self.assertTrue(RemoteFile.objects.filter(pk=cached.pk).exists())
        self.assertTrue(FileConfig.objects.filter(pk=self.host.pk).exists())

    def test_creation_preserves_project_host_list(self):
        before = self.client.get('/api/file-configs/', {'scope': 'hosts'})
        for path in ['/etc/app', '/srv/app']:
            response = self.client.post('/api/file-configs/', {**self.payload, 'file_path': path}, format='json')
            self.assertEqual(response.status_code, 201)
        after = self.client.get('/api/file-configs/', {'scope': 'hosts'})
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.data, before.data)
        self.assertEqual(FileConfig.objects.count(), 3)

    def test_legacy_file_records_are_linked_without_deleting_data(self):
        from importlib import import_module
        from django.apps import apps
        legacy = FileConfig.objects.create(
            project_node=self.host.project_node, project=self.host.project,
            host_name=self.host.host_name, ip_address=self.host.ip_address,
            port=self.host.port, account=self.account, file_path='/legacy',
        )
        migration = import_module('dashboard.migrations.0016_backfill_fileconfig_hosts')
        migration.link_file_configs_to_hosts(apps, None)
        migration.link_file_configs_to_hosts(apps, None)
        legacy.refresh_from_db()
        self.assertEqual(legacy.host_config_id, self.host.pk)
        self.assertEqual(legacy.file_path, '/legacy')
        self.assertEqual(FileConfig.objects.count(), 2)
        response = self.client.get('/api/file-configs/', {'scope': 'hosts'})
        self.assertEqual([item['id'] for item in response.data], [self.host.pk])

    def test_selection_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post('/api/file-configs/', self.payload, format='json')
        self.assertEqual(response.status_code, 401)

    def test_host_cannot_be_deleted_while_file_configs_are_linked(self):
        created = self.client.post('/api/file-configs/', self.payload, format='json')
        response = self.client.delete(f"/api/file-configs/{self.host.pk}/", data={'revision': self.host.revision}, format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(response.status_code, 400)
        self.assertIn('先删除文件管理记录', response.data['detail'])
        self.assertTrue(FileConfig.objects.filter(pk=self.host.pk).exists())
        self.assertEqual(self.client.delete(f"/api/file-configs/{created.data['id']}/", data={'revision': created.data['revision']}, format='json').status_code, 204)
        self.assertEqual(self.client.delete(f"/api/file-configs/{self.host.pk}/", data={'revision': self.host.revision}, format='json').status_code, 204)

    def test_project_batch_delete_rejects_linked_file_configs(self):
        created = self.client.post('/api/file-configs/', self.payload, format='json')
        response = self.client.post('/api/file-configs/batch/', {
            'action': 'delete', 'items': [{'id': self.host.pk, 'revision': self.host.revision}],
        }, format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['results'][0]['success'])
        self.assertIn('先删除文件管理记录', response.data['results'][0]['error'])
        self.assertTrue(FileConfig.objects.filter(pk=self.host.pk).exists())
