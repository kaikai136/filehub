from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('dashboard', '0017_login_security')]
    operations = [
        migrations.AddField(
            model_name='usertwofactor',
            name='required',
            field=models.BooleanField(default=False),
        ),
    ]
