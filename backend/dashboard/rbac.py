from functools import wraps

from rest_framework.response import Response
from rest_framework import status

from .permissions import has_any_permission, has_permission


def require_permission(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not has_permission(request.user, permission):
                return Response({"detail": "没有执行此操作的权限"}, status=status.HTTP_403_FORBIDDEN)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def require_any_permission(*permissions):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not has_any_permission(request.user, *permissions):
                return Response({"detail": "没有执行此操作的权限"}, status=status.HTTP_403_FORBIDDEN)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def require_method_permissions(mapping):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            permission = mapping.get(request.method)
            allowed = has_any_permission(request.user, *permission) if isinstance(permission, tuple) else has_permission(request.user, permission) if permission else False
            if not allowed:
                return Response({"detail": "没有执行此操作的权限"}, status=status.HTTP_403_FORBIDDEN)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def require_superuser(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({"detail": "仅超级管理员可以执行此操作"}, status=status.HTTP_403_FORBIDDEN)
        return view(request, *args, **kwargs)
    return wrapped


def require_config_access(view):
    """Project hosts and file paths share records, but have distinct UI actions."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method == 'GET':
            permissions = ('file_configs.view', 'projects.view', 'file_lists.view')
        elif request.method == 'POST':
            if 'source_config_id' in request.data:
                permissions = ('file_configs.create',)
            else:
                permissions = ('projects.create',)
        elif request.method == 'PATCH':
            changed_fields = set(request.data) - {'revision'}
            permissions = ('file_configs.edit',) if changed_fields <= {'file_path'} else ('projects.edit',)
        else:
            permissions = ('file_configs.delete',)
        if not has_any_permission(request.user, *permissions):
            return Response({'detail': '没有执行此操作的权限'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped
