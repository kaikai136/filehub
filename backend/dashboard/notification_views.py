from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ConfigNotification, ConfigNotificationRead
from .notifications import notification_message
from .rbac import require_permission


def serialize_notification(notification):
    return {
        "id": notification.id,
        "event_type": notification.event_type,
        "operator": notification.operator_name or notification.operator_username or "系统",
        "operator_username": notification.operator_username,
        "occurred_at": notification.created_at.isoformat(),
        "project": notification.project_name,
        "host_name": notification.host_name,
        "ip_address": notification.ip_address,
        "path": notification.path,
        "previous_path": notification.previous_path,
        "file_config_id": notification.file_config_id,
        "file_config_id_snapshot": notification.file_config_id_snapshot,
        "message": notification_message(notification),
        "is_read": bool(notification.is_read),
    }


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("file_configs.view")
def notifications(request):
    try:
        limit = int(request.query_params.get("limit", 20))
    except (TypeError, ValueError) as error:
        raise ValidationError({"limit": "limit 必须是整数"}) from error
    limit = max(1, min(limit, 20))
    read_rows = ConfigNotificationRead.objects.filter(notification_id=OuterRef("pk"), user=request.user)
    queryset = ConfigNotification.objects.annotate(is_read=Exists(read_rows))
    items = list(queryset[:limit])
    unread_count = queryset.filter(is_read=False).count()
    serialized = [serialize_notification(item) for item in items]
    return Response({
        "items": serialized,
        "unread_count": unread_count,
        "latest": serialized[0] if serialized else None,
    })


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("file_configs.view")
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(ConfigNotification, pk=notification_id)
    ConfigNotificationRead.objects.get_or_create(notification=notification, user=request.user)
    return Response({"detail": "已标记为已读"})


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("file_configs.view")
def mark_all_notifications_read(request):
    unread_ids = ConfigNotification.objects.exclude(reads__user=request.user).values_list("id", flat=True)
    now = timezone.now()
    ConfigNotificationRead.objects.bulk_create(
        [ConfigNotificationRead(notification_id=notification_id, user=request.user, read_at=now) for notification_id in unread_ids],
        ignore_conflicts=True,
    )
    return Response({"detail": "全部通知已读"})
