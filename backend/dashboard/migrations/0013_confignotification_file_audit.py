from django.db import migrations, models
import django.db.models.deletion


def backfill_file_audit_notifications(apps, schema_editor):
    FileAudit = apps.get_model("dashboard", "FileAudit")
    ConfigNotification = apps.get_model("dashboard", "ConfigNotification")
    database = schema_editor.connection.alias

    audits = FileAudit.objects.using(database).select_related("file_config").order_by("id")
    for audit in audits.iterator():
        config = audit.file_config
        notification = ConfigNotification.objects.using(database).create(
            event_type="updated",
            operator_id=audit.operator_id,
            operator_name=audit.operator_name,
            operator_username=audit.operator_username,
            project_name=audit.project_name,
            host_name=config.host_name if config else "",
            ip_address=audit.ip_address,
            path=audit.directory,
            file_config_id=audit.file_config_id,
            file_config_id_snapshot=audit.file_config_id,
            file_audit_id=audit.id,
        )
        ConfigNotification.objects.using(database).filter(pk=notification.pk).update(created_at=audit.changed_at)


def remove_backfilled_notifications(apps, schema_editor):
    ConfigNotification = apps.get_model("dashboard", "ConfigNotification")
    ConfigNotification.objects.using(schema_editor.connection.alias).filter(file_audit_id__isnull=False).delete()


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0012_confignotification_confignotificationread")]

    operations = [
        migrations.AddField(
            model_name="confignotification",
            name="file_audit",
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="config_notification", to="dashboard.fileaudit",
            ),
        ),
        migrations.RunPython(backfill_file_audit_notifications, remove_backfilled_notifications),
    ]
