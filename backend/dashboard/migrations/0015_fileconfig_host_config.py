from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('dashboard', '0014_command_execution')]

    operations = [
        migrations.AddField(
            model_name='fileconfig',
            name='host_config',
            field=models.ForeignKey(
                to='dashboard.fileconfig', null=True, blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='path_configs', editable=False,
            ),
        ),
    ]
