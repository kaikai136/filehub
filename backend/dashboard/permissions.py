PERMISSION_GROUPS = [
    {"key": "dashboard", "label": "概览", "permissions": [("view", "查看")]},
    {"key": "projects", "label": "项目管理", "permissions": [("view", "查看"), ("create", "新增"), ("edit", "编辑"), ("delete", "删除"), ("execute", "执行"), ("import", "导入"), ("export", "导出")]},
    {"key": "accounts", "label": "SSH 账号", "permissions": [("view", "查看"), ("create", "新增"), ("edit", "编辑"), ("delete", "删除")]},
    {"key": "file_configs", "label": "文件管理", "permissions": [("view", "查看"), ("create", "新增"), ("edit", "编辑"), ("delete", "删除"), ("execute", "执行")]},
    {"key": "file_lists", "label": "文件列表", "permissions": [("view", "查看"), ("edit", "编辑")]},
    {"key": "file_audit", "label": "文件审计", "permissions": [("view", "查看"), ("delete", "删除")]},
    {"key": "operation_audit", "label": "操作审计", "permissions": [("view", "查看"), ("delete", "删除")]},
    {"key": "command_execution", "label": "命令执行", "permissions": [("view", "查看"), ("execute", "执行")]},
    {"key": "settings", "label": "设置", "permissions": [("view", "查看")]},
    {"key": "users", "label": "用户管理", "permissions": [("view", "查看"), ("create", "新增"), ("edit", "编辑"), ("delete", "删除")]},
    {"key": "roles", "label": "角色管理", "permissions": [("view", "查看"), ("create", "新增"), ("edit", "编辑"), ("delete", "删除")]},
    {"key": "command_control", "label": "命令控制", "permissions": [("view", "查看")]},
]

PERMISSION_CATALOG = [
    {"key": f"{group['key']}.{action}", "module": group["key"], "module_label": group["label"], "action": action, "action_label": label}
    for group in PERMISSION_GROUPS
    for action, label in group["permissions"]
]
ALL_PERMISSIONS = {item["key"] for item in PERMISSION_CATALOG}
READ_PERMISSIONS = {item["key"] for item in PERMISSION_CATALOG if item["action"] == "view"}


def normalize_permissions(values):
    result = {value for value in values if value in ALL_PERMISSIONS}
    result.update(f"{value.split('.')[0]}.view" for value in list(result))
    return sorted(result)


def role_permissions(user):
    if not user or not user.is_authenticated or not user.is_active:
        return set()
    if user.is_superuser:
        return set(ALL_PERMISSIONS)
    result = set()
    for role in user.roles.filter(is_active=True):
        result.update(permission for permission in role.permissions if permission in ALL_PERMISSIONS)
    return set(normalize_permissions(result))


def has_permission(user, permission):
    return permission in role_permissions(user)


def has_any_permission(user, *permissions):
    effective = role_permissions(user)
    return bool(effective.intersection(permissions))


def can_assign_permissions(user, permissions):
    if user.is_superuser:
        return True
    return set(permissions).issubset(role_permissions(user))
