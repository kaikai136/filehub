from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0019_refresh_permission_catalog")]

    operations = [
        migrations.AddField(
            model_name="systemsetting",
            name="github_url",
            field=models.URLField(default="https://github.com/", max_length=500),
        ),
    ]
