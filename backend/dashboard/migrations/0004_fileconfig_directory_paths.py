from django.db import migrations, models


def infer_directories(apps, schema_editor):
    FileConfig = apps.get_model("dashboard", "FileConfig")
    for config in FileConfig.objects.using(schema_editor.connection.alias).all().iterator():
        directories = set()
        for path in config.remote_files.values_list("relative_path", flat=True):
            parts = path.split("/")
            if not path.startswith("/"):
                directories.update("/".join(parts[:index]) for index in range(1, len(parts)))
        config.directory_paths = sorted(directories)
        config.save(update_fields=["directory_paths"])


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0003_independent_machine_accounts")]
    operations = [
        migrations.AddField(
            model_name="fileconfig", name="directory_paths",
            field=models.JSONField(default=list, editable=False),
        ),
        migrations.RunPython(infer_directories, migrations.RunPython.noop),
    ]
