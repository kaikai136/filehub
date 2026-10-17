from django.db import migrations


def link_file_configs_to_hosts(apps, schema_editor):
    FileConfig = apps.get_model('dashboard', 'FileConfig')
    hosts = {}
    for config in FileConfig.objects.filter(host_config__isnull=True).order_by('id'):
        if not config.file_path.strip():
            hosts.setdefault((config.project_node_id, config.host_name, config.ip_address, config.port), config)
    for config in FileConfig.objects.filter(host_config__isnull=True).exclude(file_path='').order_by('id'):
        host = hosts.get((config.project_node_id, config.host_name, config.ip_address, config.port))
        if host and host.pk != config.pk:
            config.host_config_id = host.pk
            config.save(update_fields=['host_config'])


class Migration(migrations.Migration):
    dependencies = [('dashboard', '0015_fileconfig_host_config')]
    operations = [migrations.RunPython(link_file_configs_to_hosts, migrations.RunPython.noop)]
