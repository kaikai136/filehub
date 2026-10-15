from django.db import migrations, models


def snapshot_accounts(apps, schema_editor):
    FileConfig = apps.get_model("dashboard", "FileConfig")
    for config in FileConfig.objects.using(schema_editor.connection.alias).select_related("account").iterator():
        config.account_snapshot = {
            field: getattr(config.account, field)
            for field in (
                "name", "username", "encrypted_password", "encrypted_private_key", "is_active",
            )
        }
        config.save(update_fields=["account_snapshot"])


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0002_fileconfig_connection_error_and_more")]

    operations = [
        migrations.AddField(
            model_name="fileconfig",
            name="account_snapshot",
            field=models.JSONField(default=dict, editable=False),
        ),
        migrations.AddField(
            model_name="fileconfig",
            name="revision",
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
        migrations.RunPython(snapshot_accounts, migrations.RunPython.noop),
    ]
