from datetime import datetime
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import update_last_login
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, F
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Account, FileConfig, OperationAudit, Project, RemoteFile
from .audit import record_file_audit, record_operation_audit
from .permissions import role_permissions
from .rbac import require_any_permission, require_config_access, require_method_permissions, require_permission, require_superuser
from .security import decrypt_value, encrypt_value
from .ssh import connect, list_remote_files, read_remote_file, test_connection, write_remote_file
from .projects import resolve_project, validate_config
from .system_metrics import collect_system_metrics


UserModel = get_user_model()


def serialize_user(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "name": user.get_full_name() or user.username,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "date_joined": user.date_joined.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "roles": [{"id": role.id, "name": role.name, "code": role.code, "is_active": role.is_active} for role in user.roles.all()],
        "permissions": sorted(role_permissions(user)),
    }


def serialize_account(account):
    return {
        "id": account.id,
        "name": account.name,
        "username": account.username,
        "note": account.note,
        "is_active": account.is_active,
        "has_password": bool(account.encrypted_password),
        "has_private_key": bool(account.encrypted_private_key),
        "created_at": account.created_at.isoformat(),
        "updated_at": account.updated_at.isoformat(),
    }


def serialize_file_config(config):
    return {
        "id": config.id,
        "project": config.project,
        "project_id": config.project_node_id,
        "project_path": config.project_node.path if config.project_node_id else config.project,
        "specifications": config.specifications,
        "platform_type": config.platform_type,
        "inspection_status": config.inspection_status,
        "inspection_error": config.inspection_error,
        "last_inspected_at": config.last_inspected_at.isoformat() if config.last_inspected_at else None,
        "host_name": config.host_name,
        "ip_address": config.ip_address,
        "machine_name": config.machine_name,
        "port": config.port,
        "file_path": config.file_path,
        "directory_paths": config.directory_paths,
        "account_id": config.account_id,
        "account_name": config.ssh_account.name,
        "revision": config.revision,
        "status": config.status,
        "connection_status": config.connection_status,
        "connection_error": config.connection_error,
        "last_verified_at": config.last_verified_at.isoformat() if config.last_verified_at else None,
        "fetch_status": config.fetch_status,
        "fetch_error": config.fetch_error,
        "file_count": config.file_count if hasattr(config, "file_count") else config.remote_files.count(),
        "last_fetched_at": config.last_fetched_at.isoformat() if config.last_fetched_at else None,
        "last_error": config.last_error,
        "created_at": config.created_at.isoformat(),
        "updated_at": config.updated_at.isoformat(),
    }


def serialize_remote_file(remote_file):
    return {
        "id": remote_file.id,
        "file_config_id": remote_file.file_config_id,
        "project": remote_file.project,
        "name": remote_file.name,
        "relative_path": remote_file.relative_path,
        "file_type": remote_file.file_type,
        "size": remote_file.size,
        "modified_at": remote_file.modified_at.isoformat() if remote_file.modified_at else None,
        "fetched_at": remote_file.fetched_at.isoformat(),
    }


def ensure_development_admin():
    if not UserModel.objects.exists():
        return UserModel.objects.create_superuser(
            username="admin",
            password="admin123",
            email="admin@confighub.local",
        )
    return None


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def health(request):
    return Response({"status": "ok", "service": "ConfigHub API"})


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    username = str(request.data.get("username", "")).strip()
    password = str(request.data.get("password", ""))
    ensure_development_admin()
    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({"detail": "用户名或密码错误"}, status=status.HTTP_400_BAD_REQUEST)
    if not user.is_active:
        return Response({"detail": "该用户已被禁用"}, status=status.HTTP_403_FORBIDDEN)
    token, _ = Token.objects.get_or_create(user=user)
    update_last_login(None, user)
    user.refresh_from_db(fields=["last_login"])
    record_operation_audit(request, '认证', '登录', user.username, 'Token 登录成功', user=user)
    return Response({"token": token.key, "user": serialize_user(user)})


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def logout(request):
    record_operation_audit(request, '认证', '退出登录', request.user.username, '用户退出登录')
    Token.objects.filter(user=request.user).delete()
    return Response({"detail": "已退出登录"})


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(serialize_user(request.user))


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_superuser
def users(request):
    from .user_management import list_or_create_users
    return list_or_create_users(request)


@api_view(["PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_superuser
def user_detail(request, user_id):
    from .user_management import update_or_delete_user
    return update_or_delete_user(request, user_id)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_method_permissions({"GET": "accounts.view", "POST": "accounts.create"})
def accounts(request):
    if request.method == "GET":
        query = str(request.query_params.get("search", "")).strip()
        queryset = Account.objects.all()
        if query:
            queryset = queryset.filter(name__icontains=query) | queryset.filter(username__icontains=query)
        return Response([serialize_account(account) for account in queryset])

    data = request.data
    if not data.get("name") or not data.get("username"):
        return Response({"detail": "账号名称和用户不能为空"}, status=status.HTTP_400_BAD_REQUEST)
    account = Account.objects.create(
        name=str(data["name"]).strip(),
        username=str(data["username"]).strip(),
        encrypted_password=encrypt_value(str(data.get("password", ""))),
        encrypted_private_key=encrypt_value(str(data.get("private_key", ""))),
        note=str(data.get("note", "")).strip(),
        is_active=bool(data.get("is_active", True)),
    )
    record_operation_audit(request, 'SSH 账号', '新增', account.name, '创建 SSH 账号')
    return Response(serialize_account(account), status=status.HTTP_201_CREATED)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_any_permission('projects.create', 'projects.edit', 'projects.import', 'file_configs.edit')
def account_options(request):
    return Response([{'id': account.id, 'name': account.name, 'is_active': account.is_active} for account in Account.objects.all()])


@api_view(["PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_method_permissions({"PATCH": "accounts.edit", "DELETE": "accounts.delete"})
def account_detail(request, account_id):
    try:
        account = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        return Response({"detail": "账号不存在"}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        if account.file_configs.exists():
            return Response({"detail": "该账号已被文件管理配置引用，请先解除引用"}, status=status.HTTP_409_CONFLICT)
        object_name = account.name
        account.delete()
        record_operation_audit(request, 'SSH 账号', '删除', object_name, '删除 SSH 账号')
        return Response(status=status.HTTP_204_NO_CONTENT)

    data = request.data
    for field in ("name", "username", "note"):
        if field in data:
            setattr(account, field, str(data[field]).strip())
    if "is_active" in data:
        account.is_active = bool(data["is_active"])
    if "password" in data and str(data["password"]):
        account.encrypted_password = encrypt_value(str(data["password"]))
    if "private_key" in data and str(data["private_key"]):
        account.encrypted_private_key = encrypt_value(str(data["private_key"]))
    account.save()
    action = '启用/禁用' if set(data).issubset({'is_active'}) else '编辑'
    record_operation_audit(request, 'SSH 账号', action, account.name, '更新 SSH 账号')
    return Response(serialize_account(account))


def _get_account(account_id):
    try:
        return Account.objects.get(id=account_id)
    except Account.DoesNotExist as error:
        raise ValueError("关联账号不存在") from error


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_config_access
def file_configs(request):
    if request.method == "GET":
        query = str(request.query_params.get("search", "")).strip()
        queryset = FileConfig.objects.select_related("account", "project_node").annotate(file_count=Count("remote_files"))
        if query:
            queryset = queryset.filter(project__icontains=query) | queryset.filter(host_name__icontains=query) | queryset.filter(ip_address__icontains=query)
        return Response([serialize_file_config(config) for config in queryset])

    data = request.data
    if 'source_config_id' in data:
        if type(data['source_config_id']) is not int:
            return Response({'detail': '请选择有效机器'}, status=400)
        # Copy the selected host's own credentials, not its potentially edited
        # account template. Resolve everything again when the form is submitted.
        with transaction.atomic():
            source = FileConfig.objects.select_for_update().filter(pk=data['source_config_id']).first()
            if source is None:
                return Response({'detail': '所选机器不存在，请重新选择'}, status=400)
            if data.get('source_revision') != source.revision:
                return Response({'detail': '所选机器已更新，请重新打开新增窗口'}, status=409)
            if data.get('project_id') != source.project_node_id:
                return Response({'detail': '所选机器不属于当前项目'}, status=400)
            path = data.get('file_path')
            if not isinstance(path, str) or not path.strip() or len(path.strip()) > 500:
                return Response({'detail': '请填写有效文件路径（最多 500 字符）'}, status=400)
            config = FileConfig.objects.create(
                project_node=source.project_node, project=source.project,
                host_name=source.host_name, ip_address=source.ip_address,
                machine_name=source.machine_name, port=source.port,
                account=source.account, account_snapshot=source.account_snapshot.copy(),
                file_path=path.strip(),
            )
        record_operation_audit(request, '文件管理', '新增', config.file_path, '创建文件管理配置')
        return Response(serialize_file_config(config), status=status.HTTP_201_CREATED)
    required = ("host_name", "ip_address", "account_id")
    if any(not data.get(field) for field in required):
        return Response({"detail": "项目、主机名称、IP 地址和账号不能为空"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_config(data)
        account = _get_account(data["account_id"])
        project = resolve_project(data)
        config = FileConfig.objects.create(
            project=project.name, project_node=project,
            host_name=str(data["host_name"]).strip(),
            ip_address=str(data["ip_address"]).strip(),
            machine_name=str(data.get("machine_name", "")).strip(),
            port=int(data.get("port", 22)),
            file_path=str(data.get("file_path", "")).strip(),
            account=account,
        )
    except (ValueError, TypeError) as error:
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
    record_operation_audit(request, '项目管理', '新增', config.host_name, '创建项目主机配置')
    return Response(serialize_file_config(config), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_config_access
def file_config_detail(request, config_id):
    try:
        config = FileConfig.objects.select_related("account").get(id=config_id)
    except FileConfig.DoesNotExist:
        return Response({"detail": "文件管理配置不存在"}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        object_name = config.file_path or config.host_name
        with transaction.atomic():
            current = FileConfig.objects.select_for_update().get(pk=config.pk)
            if 'revision' in request.data and request.data['revision'] != current.revision:
                return Response({'detail': '此记录已更新，请刷新后重试'}, status=409)
            current.delete()
        record_operation_audit(request, '文件管理', '删除', object_name, '删除文件管理配置')
        return Response(status=status.HTTP_204_NO_CONTENT)
    data = request.data
    if "revision" in data and data["revision"] != config.revision:
        return Response({"detail": "此记录已更新，请重新打开后编辑"}, status=status.HTTP_409_CONFLICT)
    old_connection = (config.ip_address, config.port, config.account_id, config.account_snapshot.copy())
    old_path = config.file_path
    old_project = config.project
    old_project_node_id = config.project_node_id
    validate_config(data, config)
    config.project_node = resolve_project(data, config)
    config.project = config.project_node.name
    for field in ("host_name", "ip_address", "machine_name", "file_path"):
        if field in data:
            setattr(config, field, str(data[field]).strip())
    if "port" in data:
        config.port = int(data["port"])
    if "account_id" in data:
        try:
            config.bind_account(_get_account(data["account_id"]))
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
    connection_changed = old_connection != (config.ip_address, config.port, config.account_id, config.account_snapshot)
    if connection_changed:
        config.connection_status = "pending"
        config.connection_error = ""
        config.last_verified_at = None
        config.specifications = {}
        config.machine_name = ""
        config.platform_type = ''
        config.inspection_status = 'pending'
        config.inspection_error = ''
        config.last_inspected_at = None
    with transaction.atomic():
        # Reject stale editors rather than saving an old copy over another request.
        current = FileConfig.objects.select_for_update().get(pk=config.pk)
        if current.revision != config.revision:
            return Response({"detail": "此记录已更新，请重新打开后编辑"}, status=status.HTTP_409_CONFLICT)
        config.revision += 1
        fields = [
            "project", "project_node", "host_name", "ip_address", "machine_name", "port", "file_path",
            "account", "account_snapshot", "revision", "updated_at",
        ]
        if connection_changed:
            fields += ["connection_status", "connection_error", "last_verified_at"]
            fields += ['specifications', 'platform_type', 'inspection_status', 'inspection_error', 'last_inspected_at']
        if connection_changed or old_path != config.file_path:
            config.fetch_status = "pending"
            config.fetch_error = ""
            config.last_fetched_at = None
            config.status = "pending"
            config.last_error = ""
            config.remote_files.all().delete()
            config.directory_paths = []
            fields += ["directory_paths"]
            fields += ["fetch_status", "fetch_error", "last_fetched_at", "status", "last_error"]
        elif old_project != config.project or old_project_node_id != config.project_node_id:
            config.remote_files.update(project=config.project)
        config.save(update_fields=fields)
    config.refresh_from_db()
    record_operation_audit(request, '文件管理', '编辑', config.file_path or config.host_name, '更新文件管理配置')
    return Response(serialize_file_config(config))


def _stale_action_response(config):
    current = FileConfig.objects.filter(pk=config.pk).first()
    data = {"detail": "配置已更新，已忽略旧操作结果，请重新操作"}
    if current:
        data["config"] = serialize_file_config(current)
    return Response(data, status=status.HTTP_409_CONFLICT)


def _store_remote_result(config, fields, files=None):
    with transaction.atomic():
        current = FileConfig.objects.select_for_update().filter(pk=config.pk).first()
        if current is None or current.revision != config.revision:
            return False
        if files is not None:
            current.remote_files.all().delete()
            RemoteFile.objects.bulk_create([RemoteFile(file_config=current, **item) for item in files])
            config.directory_paths = sorted(getattr(files, "directory_paths", []))
            fields = [*fields, "directory_paths"]
        for field in fields:
            setattr(current, field, getattr(config, field))
        current.save(update_fields=[*fields, "updated_at"])
    config.refresh_from_db()
    return True


def _run_remote_action(config, refresh=False):
    # Each operation owns a revision of this record; edits and newer actions supersede it.
    if not FileConfig.objects.filter(pk=config.pk, revision=config.revision).update(revision=F("revision") + 1):
        return _stale_action_response(config)
    config.revision += 1
    # SSH authentication is independent of SFTP and the configured file path.
    try:
        if refresh:
            client = connect(config)
        else:
            test_connection(config)
    except Exception as error:
        config.connection_status = "error"
        config.connection_error = str(error)
        config.status = "error"
        config.last_error = str(error)
        fields = ["connection_status", "connection_error", "status", "last_error"]
        if refresh:
            config.fetch_status = "error"
            config.fetch_error = str(error)
            fields += ["fetch_status", "fetch_error"]
        if not _store_remote_result(config, fields):
            return _stale_action_response(config)
        return Response({"detail": str(error), "config": serialize_file_config(config)}, status=status.HTTP_400_BAD_REQUEST)
    config.connection_status = "success"
    config.connection_error = ""
    config.last_verified_at = timezone.now()
    if not _store_remote_result(config, ["connection_status", "connection_error", "last_verified_at"]):
        if refresh:
            client.close()
        return _stale_action_response(config)
    if not refresh:
        return Response({"detail": "SSH 登录验证成功", "config": serialize_file_config(config)})
    try:
        files = list_remote_files(config, client=client)
        config.fetch_status = "success"
        config.fetch_error = ""
        config.last_fetched_at = timezone.now()
        config.status = "success"
        config.last_error = ""
        if not _store_remote_result(config, ["fetch_status", "fetch_error", "last_fetched_at", "status", "last_error"], files=files):
            return _stale_action_response(config)
    except Exception as error:
        config.fetch_status = "error"
        config.fetch_error = str(error)
        config.status = "error"
        config.last_error = str(error)
        if not _store_remote_result(config, ["fetch_status", "fetch_error", "status", "last_error"]):
            return _stale_action_response(config)
        return Response({"detail": str(error), "config": serialize_file_config(config)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        "detail": f"文件列表获取成功，共 {len(files)} 个文件",
        "file_count": len(files),
        "config": serialize_file_config(config),
        "files": [serialize_remote_file(item) for item in config.remote_files.all()],
    })


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("file_configs.execute")
def file_config_test_connection(request, config_id):
    try:
        config = FileConfig.objects.select_related("account").get(id=config_id)
    except FileConfig.DoesNotExist:
        return Response({"detail": "文件管理配置不存在"}, status=status.HTTP_404_NOT_FOUND)
    response = _run_remote_action(config)
    if response.status_code < 400:
        record_operation_audit(request, '文件管理', '执行', config.file_path or config.host_name, '测试 SSH 连接')
    return response


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("file_configs.execute")
def file_config_refresh(request, config_id):
    try:
        config = FileConfig.objects.select_related("account").get(id=config_id)
    except FileConfig.DoesNotExist:
        return Response({"detail": "文件管理配置不存在"}, status=status.HTTP_404_NOT_FOUND)
    if not config.file_path.strip():
        return Response({"detail": "未配置文件路径，无法获取文件列表"}, status=status.HTTP_400_BAD_REQUEST)
    response = _run_remote_action(config, refresh=True)
    if response.status_code < 400:
        record_operation_audit(request, '文件管理', '执行', config.file_path, '获取远程文件列表')
    return response


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("file_lists.view")
def file_lists(request):
    queryset = RemoteFile.objects.select_related("file_config")
    project = str(request.query_params.get("project", "")).strip()
    if project:
        queryset = queryset.filter(project__icontains=project)
    return Response([serialize_remote_file(item) for item in queryset])


@api_view(["GET", "PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_method_permissions({"GET": "file_lists.view", "PATCH": "file_lists.edit"})
def file_content(request, file_id):
    try:
        remote_file = RemoteFile.objects.select_related("file_config").get(id=file_id)
    except RemoteFile.DoesNotExist:
        return Response({"detail": "文件不存在，请刷新文件列表"}, status=status.HTTP_404_NOT_FOUND)

    try:
        if request.method == "GET":
            content = read_remote_file(remote_file)
            return Response({"file": serialize_remote_file(remote_file), "content": content, "encoding": "utf-8"})

        content = request.data.get("content")
        if not isinstance(content, str):
            return Response({"detail": "文件内容格式无效"}, status=status.HTTP_400_BAD_REQUEST)
        before = read_remote_file(remote_file)
        attrs = write_remote_file(remote_file, content)
        remote_file.size = attrs.st_size
        remote_file.modified_at = timezone.make_aware(datetime.fromtimestamp(attrs.st_mtime)) if attrs.st_mtime else None
        remote_file.save(update_fields=["size", "modified_at", "fetched_at"])
        record_file_audit(request, remote_file, before, content)
        record_operation_audit(request, '文件列表', '编辑', remote_file.relative_path, '保存远程文件内容')
        return Response({"detail": "文件保存成功", "file": serialize_remote_file(remote_file)})
    except Exception as error:
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission("dashboard.view")
def dashboard(request):
    system_data = collect_system_metrics()
    effective_permissions = role_permissions(request.user)
    resource_definitions = [
        ("projects.view", {"key": "projects", "label": "项目", "count": Project.objects.count(), "description": "项目目录节点", "path": "/projects"}),
        ("accounts.view", {"key": "accounts", "label": "SSH 账号", "count": Account.objects.count(), "description": "已保存连接凭据", "path": "/accounts"}),
        ("file_configs.view", {"key": "configs", "label": "文件配置", "count": FileConfig.objects.count(), "description": "远程主机文件配置", "path": "/file-configs"}),
        ("file_lists.view", {"key": "files", "label": "远程文件", "count": RemoteFile.objects.count(), "description": "最近同步文件索引", "path": "/file-lists"}),
    ]
    resources = [resource for permission, resource in resource_definitions if permission in effective_permissions]
    activity = []
    if "operation_audit.view" in effective_permissions:
        records = OperationAudit.objects.select_related("operator")[:5]
        activity = [{
            "id": record.id,
            "title": f"{record.module} · {record.action}",
            "detail": record.detail or record.object_name or "操作成功",
            "operator": record.operator_name or record.operator_username or "系统",
            "occurred_at": record.occurred_at.isoformat(),
            "type": "primary",
        } for record in records]
    return Response({**system_data, "resources": resources, "activity": activity})
