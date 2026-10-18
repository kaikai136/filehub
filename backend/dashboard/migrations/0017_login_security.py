from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('dashboard', '0016_backfill_fileconfig_hosts'), ('authtoken', '0004_alter_tokenproxy_options')]
    operations = [
        migrations.CreateModel(name='LoginSession', fields=[
            ('token', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='login_session', serialize=False, to='authtoken.token')),
            ('expires_at', models.DateTimeField()),
        ]),
        migrations.AddField(model_name='systemsetting', name='login_expiry_minutes', field=models.PositiveIntegerField(default=480)),
        migrations.CreateModel(name='UserTwoFactor', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('enabled', models.BooleanField(default=False)),
            ('encrypted_secret', models.TextField(blank=True, default='')),
            ('bound_at', models.DateTimeField(blank=True, null=True)),
            ('last_step', models.BigIntegerField(default=-1)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='two_factor', to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='AuthChallenge', fields=[
            ('id', models.CharField(max_length=64, primary_key=True, serialize=False)),
            ('kind', models.CharField(max_length=20)),
            ('payload', models.JSONField(default=dict)),
            ('expires_at', models.DateTimeField()),
            ('attempts', models.PositiveSmallIntegerField(default=0)),
        ]),
    ]
