from django.db import migrations


PERMISSION_GROUPS = {
    "dashboard": ["view"],
    "projects": ["view", "create", "edit", "delete", "execute", "import", "export"],
    "accounts": ["view", "create", "edit", "delete"],
    "file_configs": ["view", "create", "edit", "delete", "execute"],
    "file_lists": ["view", "edit"],
    "file_audit": ["view", "delete"],
    "operation_audit": ["view", "delete"],
    "command_execution": ["view", "execute"],
    "settings": ["view"],
    "users": ["view", "create", "edit", "delete"],
    "roles": ["view", "create", "edit", "delete"],
    "command_control": ["view"],
}
ALL_PERMISSIONS = {f"{module}.{action}" for module, actions in PERMISSION_GROUPS.items() for action in actions}
READ_PERMISSIONS = {f"{module}.view" for module in PERMISSION_GROUPS}


def normalize(values):
    result = {value for value in values if value in ALL_PERMISSIONS}
    result.update(f"{value.split('.')[0]}.view" for value in list(result))
    return sorted(result)


def refresh_roles(apps, schema_editor):
    Role = apps.get_model("dashboard", "Role")
    for role in Role.objects.using(schema_editor.connection.alias).all():
        if role.is_builtin and role.code == "administrator":
            role.permissions = sorted(ALL_PERMISSIONS)
        elif role.is_builtin and role.code == "viewer":
            role.permissions = sorted(READ_PERMISSIONS)
        else:
            role.permissions = normalize(role.permissions)
        role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0021_commandpolicy")]
    operations = [migrations.RunPython(refresh_roles, migrations.RunPython.noop)]
