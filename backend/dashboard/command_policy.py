from .models import CommandPolicy
from .shell_safety import BLOCKED_COMMAND_GROUPS


def default_rules():
    rules = [
        {"command": command, "category": category, "match": "exact", "enabled": True}
        for category, commands in BLOCKED_COMMAND_GROUPS.items()
        for command in commands.split()
    ]
    rules.extend([
        {"command": "mkfs.", "category": "磁盘与文件系统", "match": "prefix", "enabled": True},
        {"command": "fsck.", "category": "磁盘与文件系统", "match": "prefix", "enabled": True},
        {"command": "python", "category": "脚本解释器", "match": "python_version", "enabled": True},
    ])
    return rules


def get_command_policy():
    policy, _ = CommandPolicy.objects.get_or_create(pk=1, defaults={"rules": default_rules()})
    return policy


def active_rules():
    return get_command_policy().rules
