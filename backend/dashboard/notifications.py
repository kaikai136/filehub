import logging

from django.db import transaction
from django.utils import timezone

from .models import ConfigNotification


logger = logging.getLogger(__name__)

EVENT_ACTIONS = {
    "created": "新增了",
    "updated": "更改了",
    "deleted": "删除了",
}


def _operator_values(user):
    if not user or not getattr(user, "is_authenticated", False):
        return {"operator": None, "operator_name": "系统", "operator_username": ""}
    return {
        "operator": user,
        "operator_name": user.get_full_name() or user.username,
        "operator_username": user.username,
    }


def config_snapshot(config):
    project = config.project_node.path if config.project_node_id else config.project
    return {
        "project_name": project,
        "host_name": config.host_name,
        "ip_address": config.ip_address,
        "path": config.file_path,
        "file_config_id_snapshot": config.pk,
    }


def record_config_notification(request, event_type, config=None, snapshot=None, previous_path="", file_audit=None):
    if event_type not in EVENT_ACTIONS:
        raise ValueError("Unsupported config notification event")
    values = dict(snapshot or config_snapshot(config))
    values.update(_operator_values(getattr(request, "user", None)))
    values.update({
        "event_type": event_type,
        "previous_path": previous_path,
        "file_config": config if config and config.pk else None,
        "file_audit": file_audit,
    })
    try:
        with transaction.atomic():
            return ConfigNotification.objects.create(**values)
    except Exception:
        logger.exception("Failed to persist config notification")
        return None


def notification_message(notification):
    timestamp = timezone.localtime(notification.created_at).strftime("%Y-%m-%d %H:%M:%S")
    operator = notification.operator_name or notification.operator_username or "系统"
    machine = notification.host_name
    if notification.ip_address:
        machine = f"{machine}（{notification.ip_address}）" if machine else str(notification.ip_address)
    action = EVENT_ACTIONS.get(notification.event_type, "更改了")
    path = notification.path or "未设置文件路径"
    return f"{operator} {timestamp} {action} {machine} {path} 的配置"
