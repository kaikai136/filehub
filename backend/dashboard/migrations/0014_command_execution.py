from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def add_command_permissions(apps, schema_editor):
    Role = apps.get_model("dashboard", "Role")
    for role in Role.objects.using(schema_editor.connection.alias).filter(is_builtin=True):
        permissions = set(role.permissions)
        permissions.add("command_execution.view")
        if role.code == "administrator":
            permissions.add("command_execution.execute")
        role.permissions = sorted(permissions)
        role.save(update_fields=["permissions"])


def remove_command_permissions(apps, schema_editor):
    Role = apps.get_model("dashboard", "Role")
    for role in Role.objects.using(schema_editor.connection.alias).all():
        role.permissions = [value for value in role.permissions if not value.startswith("command_execution.")]
        role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0013_confignotification_file_audit"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CommandExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operator_name", models.CharField(blank=True, default="", max_length=255)),
                ("operator_username", models.CharField(blank=True, default="", max_length=150)),
                ("project_name", models.CharField(blank=True, default="", max_length=500)),
                ("host_name", models.CharField(blank=True, default="", max_length=150)),
                ("ip_address", models.GenericIPAddressField()),
                ("port", models.PositiveIntegerField(default=22)),
                ("mode", models.CharField(choices=[("shell", "Shell"), ("k8s", "K8s")], max_length=20)),
                ("working_directory", models.CharField(default="/root", max_length=500)),
                ("file_path", models.CharField(blank=True, default="", max_length=1000)),
                ("command", models.TextField()),
                ("status", models.CharField(choices=[("queued", "排队中"), ("running", "执行中"), ("succeeded", "成功"), ("failed", "失败"), ("stopped", "已停止"), ("timeout", "超时")], default="queued", max_length=20)),
                ("exit_code", models.IntegerField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, default="")),
                ("output_truncated", models.BooleanField(default=False)),
                ("stop_requested", models.BooleanField(default=False)),
                ("requested_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("file_config", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="command_executions", to="dashboard.fileconfig")),
                ("operator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="command_executions", to=settings.AUTH_USER_MODEL)),
                ("remote_file", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="command_executions", to="dashboard.remotefile")),
            ],
            options={"ordering": ["-created_at", "-id"], "indexes": [models.Index(fields=["-created_at"], name="command_exec_time_idx"), models.Index(fields=["status", "-created_at"], name="command_exec_status_idx"), models.Index(fields=["operator", "-created_at"], name="command_exec_user_idx")]},
        ),
        migrations.CreateModel(
            name="CommandExecutionOutput",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stream", models.CharField(choices=[("stdout", "stdout"), ("stderr", "stderr")], max_length=10)),
                ("sequence", models.PositiveIntegerField()),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("execution", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outputs", to="dashboard.commandexecution")),
            ],
            options={"ordering": ["sequence"], "constraints": [models.UniqueConstraint(fields=("execution", "sequence"), name="unique_command_output_sequence")]},
        ),
        migrations.RunPython(add_command_permissions, remove_command_permissions),
    ]
