from django.contrib.auth import get_user_model
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Role
from .audit import record_operation_audit

UserModel = get_user_model()


class UserPayload(serializers.Serializer):
    username = serializers.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    role_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)
    is_active = serializers.BooleanField(required=False)

    def validate_password(self, value):
        if value and len(value) < 6:
            raise serializers.ValidationError('密码至少 6 位')
        return value


def validated_payload(request, user=None):
    forbidden = {'is_staff', 'is_superuser', 'permissions', 'groups', 'user_permissions'} & set(request.data)
    if forbidden:
        raise ValidationError({'detail': '只能通过角色分配业务权限，不能修改管理员标志'})
    payload = UserPayload(data=request.data, partial=user is not None)
    if not payload.is_valid():
        first = next(iter(payload.errors.values()))
        raise ValidationError({'detail': str(first[0])})
    data = payload.validated_data
    if user is None and not data.get('password'):
        raise ValidationError({'detail': '请输入至少 6 位密码'})
    if user is None and not data.get('role_ids'):
        raise ValidationError({'detail': '请至少选择一个角色'})
    if user is not None and 'username' in data and data['username'] != user.username:
        raise ValidationError({'detail': '登录名创建后不可修改'})
    return data


def selected_roles(data, user=None):
    if 'role_ids' not in data:
        return None
    ids = set(data['role_ids'])
    roles = list(Role.objects.select_for_update().filter(pk__in=ids))
    if len(roles) != len(ids):
        raise ValidationError({'detail': '请选择有效角色'})
    existing = set(user.roles.values_list('id', flat=True)) if user else set()
    if any(not role.is_active and role.pk not in existing for role in roles):
        raise ValidationError({'detail': '不能分配已禁用的角色'})
    return roles


def list_or_create_users(request):
    from .views import serialize_user
    if request.method == 'GET':
        return Response([serialize_user(user) for user in UserModel.objects.prefetch_related('roles').order_by('-date_joined')])
    data = validated_payload(request)
    try:
        with transaction.atomic():
            roles = selected_roles(data)
            user = UserModel.objects.create_user(username=data['username'], first_name=data['name'], email=data.get('email', ''), password=data['password'], is_active=data.get('is_active', True))
            user.roles.set(roles)
    except IntegrityError:
        raise ValidationError({'detail': '登录名已存在'})
    record_operation_audit(request, '用户管理', '新增', user.username, '创建用户')
    return Response(serialize_user(user), status=201)


@transaction.atomic
def update_or_delete_user(request, user_id):
    from .views import serialize_user
    # Lock roles before users, consistently with membership changes and role deletion.
    list(Role.objects.select_for_update().values_list('pk', flat=True))
    users = list(UserModel.objects.select_for_update().all())
    user = next((item for item in users if item.pk == user_id), None)
    if user is None:
        return Response({'detail': '用户不存在'}, status=404)
    data = validated_payload(request, user) if request.method != 'DELETE' else {}
    destructive = request.method == 'DELETE' or data.get('is_active') is False
    if destructive and user.pk == request.user.pk:
        return Response({'detail': '不能停用或删除当前登录用户'}, status=400)
    if destructive and user.is_superuser and user.is_active and not any(item.is_superuser and item.is_active and item.pk != user.pk for item in users):
        return Response({'detail': '不能停用或删除最后一个有效超级管理员'}, status=400)
    if request.method == 'DELETE':
        object_name = user.username
        user.delete()
        record_operation_audit(request, '用户管理', '删除', object_name, '删除用户')
        return Response(status=204)
    roles = selected_roles(data, user)
    for key, attribute in [('name', 'first_name'), ('email', 'email'), ('is_active', 'is_active')]:
        if key in data:
            setattr(user, attribute, data[key])
    if 'name' in data:
        user.last_name = ''
    if data.get('password'):
        user.set_password(data['password'])
    user.save()
    if roles is not None:
        user.roles.set(roles)
    if not user.is_active or data.get('password'):
        Token.objects.filter(user=user).delete()
    action = '启用/禁用' if 'is_active' in data and set(data).issubset({'is_active', 'role_ids'}) else '编辑'
    record_operation_audit(request, '用户管理', action, user.username, '更新用户')
    return Response(serialize_user(user))
