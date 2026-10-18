import re

from django.db import transaction
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .authentication import ExpiryTokenAuthentication as TokenAuthentication
from .audit import record_operation_audit
from .command_policy import default_rules, get_command_policy
from .models import CommandPolicy
from .rbac import require_permission


def serialize_policy(policy, user):
    return {"rules": policy.rules, "defaults": default_rules(), "revision": policy.revision,
            "updated_at": policy.updated_at.isoformat(), "can_edit": user.is_superuser}


def validate_rules(rules):
    if not isinstance(rules, list) or len(rules) > 500:
        return "黑名单必须是最多 500 条的规则列表"
    seen = set()
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {"command", "category", "match", "enabled"}:
            return "规则格式无效"
        command, category, match = rule["command"], rule["category"], rule["match"]
        if not isinstance(command, str) or not re.fullmatch(r"[A-Za-z0-9_.+-]{1,80}", command):
            return "命令名称须为 1 至 80 位字母、数字或 _ . + -，不能包含路径、参数或空格"
        if not isinstance(category, str) or not category.strip() or len(category) > 80:
            return "规则分类须为 1 至 80 个字符"
        if match not in ("exact", "prefix", "python_version") or (match == "python_version" and command != "python"):
            return "匹配方式无效；Python 版本匹配仅适用于 python"
        if type(rule["enabled"]) is not bool:
            return "启用状态必须为布尔值"
        key = (command, match)
        if key in seen:
            return "命令名称与匹配方式不能重复"
        seen.add(key)
    return None


@api_view(["GET", "PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("command_control.view")
def command_control(request):
    policy = get_command_policy()
    if request.method == "GET":
        return Response(serialize_policy(policy, request.user))
    if not request.user.is_superuser:
        return Response({"detail": "只有超级管理员可以修改命令控制"}, status=403)
    if not isinstance(request.data, dict):
        return Response({"detail": "命令控制数据格式无效"}, status=400)
    error = validate_rules(request.data.get("rules"))
    if error:
        return Response({"detail": error}, status=400)
    revision = request.data.get("revision")
    if type(revision) is not int:
        return Response({"detail": "请提供配置版本"}, status=400)
    with transaction.atomic():
        changed = CommandPolicy.objects.filter(pk=1, revision=revision).update(
            rules=request.data["rules"], revision=revision + 1,
        )
        if not changed:
            return Response({"detail": "配置已被其他管理员修改，请刷新后重试"}, status=409)
        policy.refresh_from_db()
        policy.save(update_fields=["updated_at"])
        record_operation_audit(request, "命令控制", "修改", "Shell 命令黑名单",
                               f"版本 {policy.revision}，规则 {len(policy.rules)} 条，启用 {sum(rule['enabled'] for rule in policy.rules)} 条")
    return Response(serialize_policy(policy, request.user))
