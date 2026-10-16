from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Account, FileConfig, Project, RemoteFile


class FileHostSelectionTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(get_user_model().objects.create_user(username='file-selector'))
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

    def test_selection_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post('/api/file-configs/', self.payload, format='json')
        self.assertEqual(response.status_code, 401)
