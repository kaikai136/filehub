from django.db import migrations, models


PERMISSIONS = [
    "dashboard.view", "projects.view", "projects.create", "projects.edit", "projects.delete", "projects.execute", "projects.import", "projects.export",
    "accounts.view", "accounts.create", "accounts.edit", "accounts.delete",
    "file_configs.view", "file_configs.create", "file_configs.edit", "file_configs.delete", "file_configs.execute",
    "file_lists.view", "file_lists.edit", "monitor.view", "tasks.view",
    "logs.view", "settings.view",
]
READ_PERMISSIONS = [permission for permission in PERMISSIONS if permission.endswith(".view")]


def create_builtin_roles(apps, schema_editor):
    Role = apps.get_model("dashboard", "Role")
    User = apps.get_model("auth", "User")
    administrator = Role.objects.create(name="管理员", code="administrator", is_active=True, permissions=PERMISSIONS, is_builtin=True)
    viewer = Role.objects.create(name="只读用户", code="viewer", is_active=True, permissions=READ_PERMISSIONS, is_builtin=True)
    administrator.users.add(*User.objects.filter(is_staff=True))
    viewer.users.add(*User.objects.filter(is_staff=False, is_superuser=False))


def remove_builtin_roles(apps, schema_editor):
    apps.get_model("dashboard", "Role").objects.filter(code__in=["administrator", "viewer"]).delete()


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0007_optional_host_metadata")]
    operations = [
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="角色名称")),
                ("code", models.CharField(max_length=100, unique=True, verbose_name="角色标识")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用状态")),
                ("permissions", models.JSONField(default=list, verbose_name="权限标识")),
                ("is_builtin", models.BooleanField(default=False, editable=False, verbose_name="内置角色")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="role", name="users",
            field=models.ManyToManyField(blank=True, related_name="roles", to="auth.user"),
        ),
        migrations.RunPython(create_builtin_roles, remove_builtin_roles),
    ]
