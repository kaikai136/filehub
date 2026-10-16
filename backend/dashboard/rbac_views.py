import re

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Role
from .permissions import ALL_PERMISSIONS, PERMISSION_CATALOG, normalize_permissions
from .rbac import require_superuser


ROLE_CODE = re.compile(r"^[a-z0-9_]+$")


def serialize_role(role):
    return {
        "id": role.id,
        "name": role.name,
        "code": role.code,
        "is_active": role.is_active,
        "permissions": normalize_permissions(role.permissions),
        "is_builtin": role.is_builtin,
        "user_count": role.users.count(),
        "created_at": role.created_at.isoformat(),
        "updated_at": role.updated_at.isoformat(),
    }


def validate_role(data, current=None):
    name = str(data.get("name", current.name if current else "")).strip()
    code = str(data.get("code", current.code if current else "")).strip()
    if not name or len(name) > 100:
        return None, "角色名称不能为空且不能超过 100 字符"
    if not code or len(code) > 100 or not ROLE_CODE.fullmatch(code):
        return None, "角色标识只能包含小写字母、数字和下划线"
    raw_permissions = data.get("permissions", current.permissions if current else [])
    if not isinstance(raw_permissions, list) or any(not isinstance(value, str) for value in raw_permissions):
        return None, "权限集合格式无效"
    if set(raw_permissions) - ALL_PERMISSIONS:
        return None, "权限集合包含无效标识"
    permissions = normalize_permissions(raw_permissions)
    if "is_active" in data and type(data["is_active"]) is not bool:
        return None, "启用状态格式无效"
    return {"name": name, "code": code, "permissions": permissions}, None


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_superuser
def permission_catalog(request):
    return Response(PERMISSION_CATALOG)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_superuser
def roles(request):
    if request.method == "GET":
        return Response([serialize_role(role) for role in Role.objects.prefetch_related("users")])
    values, error = validate_role(request.data)
    if error:
        return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
    try:
        with transaction.atomic():
            role = Role.objects.create(**values, is_active=bool(request.data.get("is_active", True)))
    except IntegrityError:
        return Response({"detail": "角色名称或角色标识已存在"}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serialize_role(role), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_superuser
@transaction.atomic
def role_detail(request, role_id):
    role = get_object_or_404(Role.objects.select_for_update(), pk=role_id)
    if role.is_builtin:
        return Response({"detail": "内置角色不可修改、停用或删除"}, status=status.HTTP_400_BAD_REQUEST)
    if request.method == "DELETE":
        if role.users.exists():
            return Response({"detail": "角色仍有关联用户，不能删除"}, status=status.HTTP_400_BAD_REQUEST)
        role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    if "code" in request.data and str(request.data["code"]).strip() != role.code:
        return Response({"detail": "角色标识创建后不可修改"}, status=status.HTTP_400_BAD_REQUEST)
    values, error = validate_role(request.data, role)
    if error:
        return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
    try:
        with transaction.atomic():
            locked = Role.objects.select_for_update().get(pk=role.pk)
            locked.name = values["name"]
            locked.permissions = values["permissions"]
            if "is_active" in request.data:
                locked.is_active = bool(request.data["is_active"])
            locked.save()
            role = locked
    except IntegrityError:
        return Response({"detail": "角色名称已存在"}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serialize_role(role))


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_superuser
def role_users(request, role_id):
    role = get_object_or_404(Role, pk=role_id)
    return Response([{
        "id": user.id, "username": user.username, "name": user.get_full_name() or user.username,
        "is_active": user.is_active,
    } for user in role.users.order_by("username")])
