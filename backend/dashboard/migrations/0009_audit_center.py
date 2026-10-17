from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_audit_permissions(apps, schema_editor):
    Role = apps.get_model('dashboard', 'Role')
    for role in Role.objects.using(schema_editor.connection.alias).all():
        permissions = set(role.permissions)
        if 'logs.view' in permissions or role.is_builtin:
            permissions.update(['file_audit.view', 'operation_audit.view'])
        permissions.discard('logs.view')
        role.permissions = sorted(permissions)
        role.save(update_fields=['permissions'])


def restore_log_permission(apps, schema_editor):
    Role = apps.get_model('dashboard', 'Role')
    for role in Role.objects.using(schema_editor.connection.alias).all():
        permissions = set(role.permissions)
        if permissions.intersection({'file_audit.view', 'operation_audit.view'}):
            permissions.add('logs.view')
        permissions.difference_update(['file_audit.view', 'operation_audit.view'])
        role.permissions = sorted(permissions)
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):
    dependencies = [
        ('dashboard', '0008_role_rbac'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='FileAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project_name', models.CharField(max_length=255, verbose_name='项目名')),
                ('project_id', models.BigIntegerField(blank=True, null=True, verbose_name='项目 ID')),
                ('ip_address', models.GenericIPAddressField(verbose_name='IP 地址')),
                ('directory', models.CharField(max_length=500, verbose_name='文件目录')),
                ('relative_path', models.CharField(max_length=500, verbose_name='文件相对路径')),
                ('operator_name', models.CharField(blank=True, default='', max_length=255)),
                ('operator_username', models.CharField(blank=True, default='', max_length=150)),
                ('changed_at', models.DateTimeField(auto_now_add=True, verbose_name='更改时间')),
                ('diff', models.TextField(verbose_name='变更内容')),
                ('file_config', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='file_audits', to='dashboard.fileconfig')),
                ('remote_file', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audits', to='dashboard.remotefile')),
                ('operator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='file_audits', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-changed_at', '-id'], 'indexes': [
                models.Index(fields=['-changed_at'], name='file_audit_time_idx'),
                models.Index(fields=['ip_address', '-changed_at'], name='file_audit_ip_time_idx'),
                models.Index(fields=['project_id', '-changed_at'], name='file_audit_project_idx'),
            ]},
        ),
        migrations.CreateModel(
            name='OperationAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('occurred_at', models.DateTimeField(auto_now_add=True, verbose_name='时间')),
                ('operator_name', models.CharField(blank=True, default='', max_length=255)),
                ('operator_username', models.CharField(blank=True, default='', max_length=150)),
                ('module', models.CharField(max_length=80, verbose_name='模块')),
                ('action', models.CharField(max_length=80, verbose_name='操作')),
                ('object_name', models.CharField(blank=True, default='', max_length=255, verbose_name='对象')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                ('detail', models.TextField(blank=True, default='', verbose_name='详情')),
                ('operator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='operation_audits', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-occurred_at', '-id'], 'indexes': [
                models.Index(fields=['-occurred_at'], name='operation_audit_time_idx'),
                models.Index(fields=['module', '-occurred_at'], name='operation_audit_module_idx'),
                models.Index(fields=['ip_address', '-occurred_at'], name='operation_audit_ip_idx'),
            ]},
        ),
        migrations.RunPython(migrate_audit_permissions, restore_log_permission),
    ]
