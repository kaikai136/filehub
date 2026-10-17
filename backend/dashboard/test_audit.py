from importlib import import_module
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Account, ConfigNotification, FileAudit, FileConfig, OperationAudit, Project, RemoteFile, Role


User = get_user_model()


class AuditTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('audit-admin', password='secret123', first_name='审计员')
        self.client.force_authenticate(self.admin)
        self.account = Account.objects.create(name='SSH', username='root')
        self.project = Project.objects.create(name='demo')
        self.config = FileConfig.objects.create(
            project='demo', project_node=self.project, host_name='node', ip_address='192.0.2.10',
            file_path='/etc/app', account=self.account,
        )
        self.remote_file = RemoteFile.objects.create(
            file_config=self.config, project='demo', name='app.yml', relative_path='conf/app.yml',
        )

    @patch('dashboard.views.write_remote_file')
    @patch('dashboard.views.read_remote_file', return_value='port: 80\nname: old\n')
    def test_file_save_creates_highlightable_diff_and_operation_audit(self, read_file, write_file):
        write_file.return_value = SimpleNamespace(st_size=25, st_mtime=1_700_000_000)
        response = self.client.patch(
            f'/api/file-lists/{self.remote_file.id}/', {'content': 'port: 8080\nname: new\n'},
            format='json', REMOTE_ADDR='198.51.100.20',
        )
        self.assertEqual(response.status_code, 200)
        audit = FileAudit.objects.get()
        self.assertEqual((audit.project_name, audit.ip_address), ('demo', '192.0.2.10'))
        self.assertEqual(audit.directory, '/etc/app/conf/app.yml')
        self.assertIn('-port: 80', audit.diff)
        self.assertIn('+port: 8080', audit.diff)
        self.assertEqual(audit.operator_username, self.admin.username)
        notification = ConfigNotification.objects.get(file_audit=audit)
        self.assertEqual(notification.event_type, 'updated')
        self.assertEqual(notification.host_name, 'node')
        self.assertEqual(notification.ip_address, '192.0.2.10')
        self.assertEqual(notification.path, '/etc/app/conf/app.yml')
        operation = OperationAudit.objects.get(module='文件列表')
        self.assertEqual((operation.action, operation.ip_address), ('编辑', '198.51.100.20'))

    @patch('dashboard.views.write_remote_file')
    @patch('dashboard.views.read_remote_file', return_value='same\n')
    def test_unchanged_file_does_not_create_file_audit(self, read_file, write_file):
        write_file.return_value = SimpleNamespace(st_size=5, st_mtime=1_700_000_000)
        response = self.client.patch(f'/api/file-lists/{self.remote_file.id}/', {'content': 'same\n'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FileAudit.objects.exists())
        self.assertFalse(ConfigNotification.objects.exists())

    def test_audit_lists_filter_order_and_paginate(self):
        older = FileAudit.objects.create(
            project_name='other', project_id=None, ip_address='192.0.2.1', directory='/a/file',
            relative_path='file', operator=self.admin, operator_name='审计员', operator_username='audit-admin', diff='-a\n+b\n',
        )
        newer = FileAudit.objects.create(
            project_name='demo/service', project_id=self.project.id, ip_address='192.0.2.10', directory='/etc/app/app.yml',
            relative_path='app.yml', operator=self.admin, operator_name='审计员', operator_username='audit-admin', diff='-x\n+y\n',
        )
        FileAudit.objects.filter(pk=older.pk).update(changed_at=timezone.now() - timedelta(days=1))
        response = self.client.get('/api/file-audits/', {
            'project': 'demo', 'ip': '192.0.2.10', 'directory': '/etc', 'operator': '审计',
            'start_time': (timezone.now() - timedelta(hours=1)).isoformat(),
            'end_time': (timezone.now() + timedelta(hours=1)).isoformat(), 'page': 1, 'page_size': 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], newer.id)
        detail = self.client.get(f'/api/file-audits/{newer.id}/')
        self.assertEqual(detail.data['diff'], newer.diff)
        self.assertEqual(self.client.get('/api/file-audits/').data['results'][0]['id'], newer.id)
        capped = self.client.get('/api/file-audits/', {'page_size': 999})
        self.assertEqual(capped.data['page_size'], 100)

    def test_operation_list_filters_and_uses_remote_addr(self):
        response = self.client.post(
            '/api/accounts/', {'name': 'created-account', 'username': 'root'},
            format='json', REMOTE_ADDR='203.0.113.8', HTTP_X_FORWARDED_FOR='10.0.0.1',
        )
        self.assertEqual(response.status_code, 201)
        audit = OperationAudit.objects.get(object_name='created-account')
        self.assertEqual(audit.ip_address, '203.0.113.8')
        listing = self.client.get('/api/operation-audits/', {
            'module': 'SSH', 'action': '新增', 'ip': '203.0.113', 'operator': '审计员', 'keyword': '创建',
        })
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data['count'], 1)
        self.assertEqual(listing.data['results'][0]['object'], 'created-account')

    def test_audit_permissions_are_independent_and_superuser_bypasses(self):
        user = User.objects.create_user('limited')
        file_role = Role.objects.create(name='文件审计查看', code='file_auditor', permissions=['file_audit.view'])
        user.roles.add(file_role)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get('/api/file-audits/').status_code, 200)
        self.assertEqual(self.client.get('/api/operation-audits/').status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/operation-audits/').status_code, 200)

    def test_legacy_log_permission_migrates_to_both_audits(self):
        role = Role.objects.create(name='旧日志查看', code='legacy_logs', permissions=['logs.view'])
        migration = import_module('dashboard.migrations.0009_audit_center')
        migration.migrate_audit_permissions(apps, SimpleNamespace(connection=connection))
        role.refresh_from_db()
        self.assertNotIn('logs.view', role.permissions)
        self.assertTrue({'file_audit.view', 'operation_audit.view'}.issubset(role.permissions))

    def test_audit_failure_does_not_fail_business_operation(self):
        with self.assertLogs('dashboard.audit', level='ERROR'):
            with patch('dashboard.audit.OperationAudit.objects.create', side_effect=RuntimeError('audit unavailable')):
                response = self.client.post('/api/accounts/', {'name': 'still-created', 'username': 'root'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Account.objects.filter(name='still-created').exists())

    def test_diff_keeps_lines_separate_without_trailing_newline(self):
        from .audit import unified_diff
        difference = unified_diff('old', 'new', '/tmp/file')
        self.assertIn('\n-old\n+new\n', difference)
