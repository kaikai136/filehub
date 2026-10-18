import posixpath
import threading

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from .authentication import ExpiryTokenAuthentication as TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .audit import client_ip, record_operation_audit
from .command_execution import (
    ACTIVE_STATUSES, MAX_GLOBAL_RUNNING, MAX_USER_RUNNING, ensure_interrupted_executions_failed,
    request_stop, start_execution,
)
from .models import CommandExecution, FileConfig, RemoteFile
from .permissions import has_permission
from .rbac import require_permission
from .shell_safety import shell_command_error
from .command_policy import active_rules


MAX_COMMAND_LENGTH = 10000
_submission_lock = threading.Lock()


def _visible_executions(user):
    queryset = CommandExecution.objects.select_related("operator", "file_config", "remote_file")
    return queryset if user.is_superuser else queryset.filter(operator=user)


def _remote_path(remote_file):
    base = remote_file.file_config.file_path.rstrip("/") or "/"
    relative = remote_file.relative_path
    return posixpath.normpath(relative if relative.startswith("/") else posixpath.join(base, relative))


def serialize_output(output):
    return {
        "id": output.id, "stream": output.stream, "sequence": output.sequence,
        "content": output.content, "created_at": output.created_at.isoformat(),
    }


def serialize_execution(execution, include_outputs=False, requesting_user=None):
    result = {
        "id": execution.id,
        "operator": execution.operator_name or execution.operator_username or "系统",
        "project": execution.project_name,
        "host_name": execution.host_name,
        "ip_address": execution.ip_address,
        "port": execution.port,
        "mode": execution.mode,
        "working_directory": execution.working_directory,
        "remote_file_id": execution.remote_file_id,
        "file_path": execution.file_path,
        "command": execution.command,
        "status": execution.status,
        "exit_code": execution.exit_code,
        "error_message": execution.error_message,
        "output_truncated": execution.output_truncated,
        "stop_requested": execution.stop_requested,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
        "created_at": execution.created_at.isoformat(),
        "can_stop": bool(
            requesting_user and has_permission(requesting_user, "command_execution.execute")
            and execution.status in ACTIVE_STATUSES
            and (requesting_user.is_superuser or execution.operator_id == requesting_user.id)
        ),
    }
    if include_outputs:
        result["outputs"] = [serialize_output(output) for output in execution.outputs.all()]
    return result


def _parse_page(request):
    try:
        page = max(1, int(request.query_params.get("page", 1)))
        page_size = max(1, min(100, int(request.query_params.get("page_size", 20))))
    except (TypeError, ValueError):
        return None, None
    return page, page_size


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("command_execution.view")
def command_options(request):
    ensure_interrupted_executions_failed()
    configs = FileConfig.objects.select_related("project_node").prefetch_related("remote_files")
    machines = []
    for config in configs:
        files = [{
            "id": item.id,
            "name": item.name,
            "relative_path": item.relative_path,
            "path": _remote_path(item),
        } for item in config.remote_files.all() if item.file_type == "file"]
        machines.append({
            "id": config.id,
            "project": config.project_node.path if config.project_node_id else config.project,
            "host_name": config.host_name,
            "ip_address": config.ip_address,
            "port": config.port,
            "files": files,
        })
    return Response({"machines": machines})


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def command_executions(request):
    ensure_interrupted_executions_failed()
    if request.method == "GET":
        if not has_permission(request.user, "command_execution.view"):
            return Response({"detail": "没有执行此操作的权限"}, status=403)
        page, page_size = _parse_page(request)
        if page is None:
            return Response({"detail": "分页参数无效"}, status=400)
        queryset = _visible_executions(request.user)
        mode = request.query_params.get("mode")
        if mode is not None:
            if mode not in {"shell", "k8s"}:
                return Response({"detail": "执行类型必须是 shell 或 k8s"}, status=400)
            queryset = queryset.filter(mode=mode)
        count = queryset.count()
        start = (page - 1) * page_size
        results = [serialize_execution(item, requesting_user=request.user) for item in queryset[start:start + page_size]]
        return Response({"count": count, "page": page, "page_size": page_size, "results": results})

    if not has_permission(request.user, "command_execution.execute"):
        return Response({"detail": "没有执行此操作的权限"}, status=403)
    data = request.data
    mode = str(data.get("mode", "")).strip()
    if mode not in {"shell", "k8s"}:
        return Response({"detail": "执行类型必须是 shell 或 k8s"}, status=400)
    try:
        config_id = int(data.get("file_config_id"))
        config = FileConfig.objects.select_related("project_node", "account").get(pk=config_id)
    except (TypeError, ValueError, FileConfig.DoesNotExist):
        return Response({"detail": "请选择有效的执行机器"}, status=400)
    working_directory = str(data.get("working_directory", "")).strip()
    if mode == "shell" and not working_directory:
        working_directory = "/root"
    if not working_directory or len(working_directory) > 500 or "\x00" in working_directory or "\n" in working_directory:
        return Response({"detail": "请输入有效的执行路径"}, status=400)

    remote_file = None
    file_path = ""
    remote_file_id = data.get("remote_file_id") if mode == "k8s" else None
    if remote_file_id not in (None, ""):
        try:
            remote_file = RemoteFile.objects.select_related("file_config").get(pk=int(remote_file_id), file_config=config, file_type="file")
        except (TypeError, ValueError, RemoteFile.DoesNotExist):
            return Response({"detail": "所选文件不属于当前执行机器"}, status=400)
        file_path = _remote_path(remote_file)

    raw_command = str(data.get("command", ""))
    command = raw_command.strip()
    if mode == "k8s" and remote_file and not command:
        import shlex
        command = f"kubectl apply -f {shlex.quote(file_path)}"
    if not command or len(raw_command) > MAX_COMMAND_LENGTH or (mode == "k8s" and "\x00" in command):
        return Response({"detail": "命令内容不能为空且不能超过 10000 个字符"}, status=400)

    if mode == "shell":
        safety_error = shell_command_error(raw_command, active_rules())
        if safety_error:
            record_operation_audit(
                request, "命令执行", "安全拦截", f"{config.host_name}（{config.ip_address}）",
                safety_error,
            )
            return Response({"detail": safety_error, "code": "dangerous_shell_command"}, status=400)

    with _submission_lock:
        active = CommandExecution.objects.filter(status__in=ACTIVE_STATUSES)
        if active.count() >= MAX_GLOBAL_RUNNING:
            return Response({"detail": "系统正在执行的命令已达到上限"}, status=409)
        if active.filter(operator=request.user).count() >= MAX_USER_RUNNING:
            return Response({"detail": "每个用户最多同时执行 2 个命令"}, status=409)

        with transaction.atomic():
            execution = CommandExecution.objects.create(
                operator=request.user,
                operator_name=request.user.get_full_name() or request.user.username,
                operator_username=request.user.username,
                file_config=config,
                project_name=config.project_node.path if config.project_node_id else config.project,
                host_name=config.host_name,
                ip_address=config.ip_address,
                port=config.port,
                mode=mode,
                working_directory=working_directory,
                remote_file=remote_file,
                file_path=file_path,
                command=command,
                requested_ip=client_ip(request),
            )
            start_execution(execution.id)
    record_operation_audit(
        request, "命令执行", "提交", f"{config.host_name}（{config.ip_address}）",
        f"任务 #{execution.id}，{mode}，路径 {working_directory}",
    )
    result = serialize_execution(execution, requesting_user=request.user)
    result["websocket_path"] = f"/ws/command-executions/{execution.id}/"
    return Response(result, status=201)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("command_execution.view")
def command_execution_detail(request, execution_id):
    ensure_interrupted_executions_failed()
    execution = get_object_or_404(_visible_executions(request.user).prefetch_related("outputs"), pk=execution_id)
    return Response(serialize_execution(execution, include_outputs=True, requesting_user=request.user))


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("command_execution.execute")
def stop_command_execution(request, execution_id):
    ensure_interrupted_executions_failed()
    execution = get_object_or_404(_visible_executions(request.user), pk=execution_id)
    if execution.status not in ACTIVE_STATUSES:
        return Response({"detail": "该命令已经结束"}, status=409)
    request_stop(execution.id)
    return Response({"detail": "正在停止命令"})
