from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0011_system_setting_watermark_mode"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfigNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("created", "新增"), ("updated", "编辑"), ("deleted", "删除")], max_length=20)),
                ("operator_name", models.CharField(blank=True, default="", max_length=255)),
                ("operator_username", models.CharField(blank=True, default="", max_length=150)),
                ("project_name", models.CharField(blank=True, default="", max_length=500)),
                ("host_name", models.CharField(blank=True, default="", max_length=150)),
                ("ip_address", models.GenericIPAddressField()),
                ("path", models.CharField(blank=True, default="", max_length=500)),
                ("previous_path", models.CharField(blank=True, default="", max_length=500)),
                ("file_config_id_snapshot", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("file_config", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="dashboard.fileconfig")),
                ("operator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="config_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["-created_at"], name="config_notice_time_idx")],
            },
        ),
        migrations.CreateModel(
            name="ConfigNotificationRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now_add=True)),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reads", to="dashboard.confignotification")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="config_notification_reads", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("notification", "user"), name="unique_config_notification_read")],
            },
        ),
    ]
