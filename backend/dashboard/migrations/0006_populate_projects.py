from django.db import migrations


def populate_projects(apps, schema_editor):
    Config = apps.get_model('dashboard', 'FileConfig')
    Project = apps.get_model('dashboard', 'Project')
    for name in Config.objects.values_list('project', flat=True).distinct():
        project, _ = Project.objects.get_or_create(name=name, parent=None)
        Config.objects.filter(project=name).update(project_node=project)


class Migration(migrations.Migration):
    dependencies = [('dashboard', '0005_project_management')]
    operations = [migrations.RunPython(populate_projects, migrations.RunPython.noop)]
