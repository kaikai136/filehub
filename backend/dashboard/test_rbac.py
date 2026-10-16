from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Account, FileConfig, Project, RemoteFile, Role
from .permissions import ALL_PERMISSIONS, READ_PERMISSIONS, role_permissions


User = get_user_model()


class RbacTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('root-admin', password='secret123')
        self.user = User.objects.create_user('operator', password='secret123', first_name='运维用户')
        self.viewer = Role.objects.get(code='viewer')
        self.administrator = Role.objects.get(code='administrator')

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_multiple_active_roles_are_unioned_and_disabled_roles_are_ignored(self):
        first = Role.objects.create(name='项目查看', code='project_reader', permissions=['projects.view'])
        second = Role.objects.create(name='账号编辑', code='account_editor', permissions=['accounts.edit'])
        self.user.roles.add(first, second)
        self.assertEqual(role_permissions(self.user), {'projects.view', 'accounts.view', 'accounts.edit'})
        second.is_active = False
        second.save(update_fields=['is_active'])
        self.assertEqual(role_permissions(self.user), {'projects.view'})

    def test_superuser_bypasses_roles_and_user_without_roles_has_no_permissions(self):
        self.assertEqual(role_permissions(self.admin), ALL_PERMISSIONS)
        self.assertEqual(role_permissions(self.user), set())
        self.authenticate(self.user)
        self.assertEqual(self.client.get('/api/dashboard/').status_code, 403)

    def test_builtin_role_permissions_match_catalog(self):
        self.assertEqual(set(self.administrator.permissions), ALL_PERMISSIONS)
        self.assertEqual(set(self.viewer.permissions), READ_PERMISSIONS)

    def test_role_code_uniqueness_format_catalog_validation_and_immutability(self):
        self.authenticate(self.admin)
        invalid = self.client.post('/api/roles/', {'name': '无效', 'code': 'Bad-Code', 'permissions': []}, format='json')
        self.assertEqual(invalid.status_code, 400)
        unknown = self.client.post('/api/roles/', {'name': '未知权限', 'code': 'unknown_permission', 'permissions': ['root.all']}, format='json')
        self.assertEqual(unknown.status_code, 400)
        created = self.client.post('/api/roles/', {'name': '发布人员', 'code': 'deployer', 'permissions': ['projects.execute']}, format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(set(created.data['permissions']), {'projects.view', 'projects.execute'})
        duplicate = self.client.post('/api/roles/', {'name': '另一个发布人员', 'code': 'deployer', 'permissions': []}, format='json')
        self.assertEqual(duplicate.status_code, 400)
        changed = self.client.patch(f"/api/roles/{created.data['id']}/", {'code': 'renamed'}, format='json')
        self.assertEqual(changed.status_code, 400)

    def test_builtin_role_is_protected_and_assigned_custom_role_cannot_be_deleted(self):
        self.authenticate(self.admin)
        for method in ('patch', 'delete'):
            response = getattr(self.client, method)(f'/api/roles/{self.viewer.id}/', {'is_active': False}, format='json')
            self.assertEqual(response.status_code, 400)
        custom = Role.objects.create(name='自定义角色', code='custom_role')
        self.user.roles.add(custom)
        self.assertEqual(self.client.delete(f'/api/roles/{custom.id}/').status_code, 400)
        self.user.roles.remove(custom)
        self.assertEqual(self.client.delete(f'/api/roles/{custom.id}/').status_code, 204)

    def test_role_and_user_management_require_superuser(self):
        self.user.roles.add(self.administrator)
        self.authenticate(self.user)
        for path in ('/api/roles/', '/api/permissions/', '/api/users/'):
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_user_role_assignment_and_me_response(self):
        self.authenticate(self.admin)
        created = self.client.post('/api/users/', {
            'username': 'created-user', 'name': '新用户', 'password': 'secret123',
            'role_ids': [self.viewer.id], 'email': 'user@example.com',
        }, format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['roles'][0]['code'], 'viewer')
        created_user = User.objects.get(username='created-user')
        self.authenticate(created_user)
        me = self.client.get('/api/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(set(me.data['permissions']), READ_PERMISSIONS)

    def test_editing_user_may_remove_all_roles_but_creation_requires_one(self):
        self.authenticate(self.admin)
        missing = self.client.post('/api/users/', {
            'username': 'no-role-at-create', 'name': '无角色', 'password': 'secret123', 'role_ids': [],
        }, format='json')
        self.assertEqual(missing.status_code, 400)
        user = User.objects.create_user('editable-user', password='secret123')
        user.roles.add(self.viewer)
        response = self.client.patch(f'/api/users/{user.id}/', {'role_ids': []}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['permissions'], [])

    def test_disabling_user_revokes_token(self):
        token = Token.objects.create(user=self.user)
        self.authenticate(self.admin)
        response = self.client.patch(f'/api/users/{self.user.id}/', {'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Token.objects.filter(key=token.key).exists())

    def test_current_user_and_last_active_superuser_are_protected(self):
        self.authenticate(self.admin)
        self.assertEqual(self.client.patch(f'/api/users/{self.admin.id}/', {'is_active': False}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/users/{self.admin.id}/').status_code, 400)
        other_admin = User.objects.create_superuser('other-admin', password='secret123')
        self.authenticate(other_admin)
        self.assertEqual(self.client.delete(f'/api/users/{self.admin.id}/').status_code, 204)
        self.authenticate(self.admin)
        # A stale authenticated instance must not bypass the database-level last-admin check.
        self.assertEqual(self.client.delete(f'/api/users/{other_admin.id}/').status_code, 400)

    def test_token_login_updates_last_login_and_returns_roles_and_permissions(self):
        self.user.roles.add(self.viewer)
        before = timezone.now()
        response = self.client.post('/api/auth/login/', {'username': self.user.username, 'password': 'secret123'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertGreaterEqual(self.user.last_login, before)
        self.assertEqual(response.data['user']['roles'][0]['code'], 'viewer')
        self.assertEqual(set(response.data['user']['permissions']), READ_PERMISSIONS)

    def test_account_api_distinguishes_view_and_write_permissions(self):
        account = Account.objects.create(name='SSH', username='root')
        role = Role.objects.create(name='账号查看', code='account_reader', permissions=['accounts.view'])
        self.user.roles.add(role)
        self.authenticate(self.user)
        self.assertEqual(self.client.get('/api/accounts/').status_code, 200)
        self.assertEqual(self.client.post('/api/accounts/', {'name': 'new', 'username': 'root'}).status_code, 403)
        self.assertEqual(self.client.patch(f'/api/accounts/{account.id}/', {'name': 'changed'}).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/accounts/{account.id}/').status_code, 403)

    def test_business_read_permissions_do_not_grant_mutation(self):
        account = Account.objects.create(name='SSH', username='root')
        project = Project.objects.create(name='demo')
        config = FileConfig.objects.create(
            project='demo', project_node=project, host_name='node', ip_address='192.0.2.1',
            file_path='/etc/app', account=account,
        )
        remote_file = RemoteFile.objects.create(
            file_config=config, project='demo', name='app.yml', relative_path='app.yml',
        )
        reader = Role.objects.create(name='业务查看', code='business_reader', permissions=[
            'projects.view', 'file_configs.view', 'file_lists.view',
        ])
        self.user.roles.add(reader)
        self.authenticate(self.user)
        for path in ('/api/projects/', '/api/file-configs/', '/api/file-lists/'):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.post('/api/projects/', {'name': 'blocked'}, format='json').status_code, 403)
        self.assertEqual(self.client.patch(
            f'/api/file-configs/{config.id}/', {'file_path': '/blocked', 'revision': config.revision}, format='json',
        ).status_code, 403)
        self.assertEqual(self.client.patch(
            f'/api/file-lists/{remote_file.id}/', {'content': 'blocked'}, format='json',
        ).status_code, 403)

