from django.contrib.auth import update_session_auth_hash
from django.db import transaction
from .authentication import ExpiryTokenAuthentication as TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .audit import purge_expired_audits, record_operation_audit
from .models import SystemSetting
from .rbac import require_permission
from .views import serialize_user


FONT_SIZES = {14, 16, 18}
WATERMARK_MODES = {"username", "custom"}


def get_system_setting():
    setting, _ = SystemSetting.objects.get_or_create(pk=1)
    return setting


def serialize_settings(setting, is_superuser=False):
    return {
        "font_size": setting.font_size,
        "watermark_enabled": setting.watermark_enabled,
        "watermark_mode": setting.watermark_mode,
        "watermark_text": setting.watermark_text,
        "watermark_opacity": setting.watermark_opacity,
        "watermark_rotation": setting.watermark_rotation,
        "file_audit_retention_days": setting.file_audit_retention_days,
        "operation_audit_retention_days": setting.operation_audit_retention_days,
        "login_expiry_minutes": setting.login_expiry_minutes,
        "can_edit_global": is_superuser,
        "updated_at": setting.updated_at.isoformat(),
    }


def validate_integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        return f"{label}必须是 {minimum} 至 {maximum} 之间的整数"
    return None


def update_user_profile(user, data):
    if not isinstance(data, dict):
        return False, "用户信息格式无效"

    name = str(data.get("name", user.get_full_name() or user.username)).strip()
    email = str(data.get("email", user.email or "")).strip()
    if not name or len(name) > 150:
        return False, "姓名不能为空且不能超过 150 个字符"
    if len(email) > 254:
        return False, "邮箱不能超过 254 个字符"

    new_password = str(data.get("new_password", ""))
    current_password = str(data.get("current_password", ""))
    if new_password:
        if len(new_password) < 6:
            return False, "新密码至少 6 位"
        if not current_password or not user.check_password(current_password):
            return False, "当前密码不正确"

    changed = False
    if name != (user.get_full_name() or user.username):
        user.first_name = name
        user.last_name = ""
        changed = True
    if email != user.email:
        user.email = email
        changed = True
    if new_password:
        user.set_password(new_password)
        changed = True
    return changed, None


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def appearance(request):
    setting = get_system_setting()
    return Response({
        "font_size": setting.font_size,
        "watermark_enabled": setting.watermark_enabled,
        "watermark_mode": setting.watermark_mode,
        "watermark_text": setting.watermark_text,
        "watermark_content": request.user.username if setting.watermark_mode == "username" else setting.watermark_text,
        "watermark_opacity": setting.watermark_opacity,
        "watermark_rotation": setting.watermark_rotation,
    })


@api_view(["GET", "PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("settings.view")
def settings(request):
    setting = get_system_setting()
    if request.method == "GET":
        return Response({"settings": serialize_settings(setting, request.user.is_superuser), "user": serialize_user(request.user)})

    user_data = request.data.get("user", {})
    global_data = request.data.get("settings", {})
    if not isinstance(user_data, dict) or not isinstance(global_data, dict):
        return Response({"detail": "设置数据格式无效"}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    user_changed, profile_error = update_user_profile(user, user_data)
    if profile_error:
        return Response({"detail": profile_error}, status=status.HTTP_400_BAD_REQUEST)

    global_changed = False
    if global_data:
        if not user.is_superuser:
            return Response({"detail": "只有超级管理员可以修改系统设置"}, status=status.HTTP_403_FORBIDDEN)
        integer_rules = {
            "font_size": ("字体大小", 14, 18),
            "watermark_opacity": ("水印透明度", 5, 60),
            "watermark_rotation": ("水印角度", -45, 45),
            "file_audit_retention_days": ("文件审计保留天数", 1, 3650),
            "operation_audit_retention_days": ("操作审计保留天数", 1, 3650),
            "login_expiry_minutes": ("系统登录过期时间", 1, 43200),
        }
        values = {}
        for field, (label, minimum, maximum) in integer_rules.items():
            if field in global_data:
                value = global_data[field]
                error = validate_integer(value, label, minimum, maximum)
                if error:
                    return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
                values[field] = value
        if "watermark_enabled" in global_data:
            if type(global_data["watermark_enabled"]) is not bool:
                return Response({"detail": "水印开关格式无效"}, status=status.HTTP_400_BAD_REQUEST)
            values["watermark_enabled"] = global_data["watermark_enabled"]
        if "watermark_text" in global_data:
            text = str(global_data["watermark_text"]).strip()
            if len(text) > 120:
                return Response({"detail": "水印文字不能超过 120 个字符"}, status=status.HTTP_400_BAD_REQUEST)
            values["watermark_text"] = text
        if "watermark_mode" in global_data:
            mode = str(global_data["watermark_mode"])
            if mode not in WATERMARK_MODES:
                return Response({"detail": "水印模式无效"}, status=status.HTTP_400_BAD_REQUEST)
            values["watermark_mode"] = mode
        effective_mode = values.get("watermark_mode", setting.watermark_mode)
        effective_text = values.get("watermark_text", setting.watermark_text)
        if effective_mode == "custom" and not effective_text:
            return Response({"detail": "自定义水印文字不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        if "font_size" in values and values["font_size"] not in FONT_SIZES:
            return Response({"detail": "字体大小只能选择 14、16 或 18"}, status=status.HTTP_400_BAD_REQUEST)
        for field, value in values.items():
            if getattr(setting, field) != value:
                setattr(setting, field, value)
                global_changed = True

    if not user_changed and not global_changed:
        return Response({"settings": serialize_settings(setting, user.is_superuser), "user": serialize_user(user)})
    with transaction.atomic():
        if user_changed:
            user.save(update_fields=["first_name", "last_name", "email", "password", "updated_at"] if hasattr(user, "updated_at") else ["first_name", "last_name", "email", "password"])
            update_session_auth_hash(request, user)
        if global_changed:
            setting.updated_by = user
            setting.save()
            purge_expired_audits()
    record_operation_audit(request, "系统设置", "编辑", user.username, "更新用户信息或系统偏好")
    return Response({"settings": serialize_settings(setting, user.is_superuser), "user": serialize_user(user)})
