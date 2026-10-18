from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0020_systemsetting_github_url")]
    operations = [
        migrations.CreateModel(
            name="CommandPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rules", models.JSONField(default=list)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
