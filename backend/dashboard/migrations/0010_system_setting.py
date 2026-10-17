from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0009_audit_center"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("font_size", models.PositiveSmallIntegerField(default=16)),
                ("watermark_enabled", models.BooleanField(default=False)),
                ("watermark_text", models.CharField(blank=True, default="FileHub", max_length=120)),
                ("watermark_opacity", models.PositiveSmallIntegerField(default=12)),
                ("watermark_rotation", models.SmallIntegerField(default=-20)),
                ("file_audit_retention_days", models.PositiveIntegerField(default=180)),
                ("operation_audit_retention_days", models.PositiveIntegerField(default=180)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_system_settings", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "系统设置"},
        ),
    ]
