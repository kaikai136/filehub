from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0010_system_setting")]

    operations = [
        migrations.AddField(
            model_name="systemsetting",
            name="watermark_mode",
            field=models.CharField(
                choices=[("username", "登录用户名"), ("custom", "自定义文字")],
                default="username",
                max_length=20,
            ),
        ),
    ]
