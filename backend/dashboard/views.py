from datetime import datetime, timedelta
from django.contrib.auth import authenticate, get_user_model
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

from .models import Account, FileConfig, RemoteFile
from .security import decrypt_value, encrypt_value
from .ssh import connect, list_remote_files, read_remote_file, test_connection, write_remote_file
from .projects import resolve_project, validate_config


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
    return Response({"token": token.key, "user": serialize_user(user)})


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def logout(request):
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
def users(request):
    if not request.user.is_staff:
        return Response({"detail": "仅管理员可以管理用户"}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "GET":
        return Response([serialize_user(user) for user in UserModel.objects.order_by("-date_joined")])

    username = str(request.data.get("username", "")).strip()
    password = str(request.data.get("password", ""))
    if not username or len(password) < 6:
        return Response({"detail": "用户名不能为空，密码至少 6 位"}, status=status.HTTP_400_BAD_REQUEST)
    if UserModel.objects.filter(username=username).exists():
        return Response({"detail": "用户名已存在"}, status=status.HTTP_400_BAD_REQUEST)
    user = UserModel.objects.create_user(
        username=username,
        password=password,
        email=str(request.data.get("email", "")).strip(),
        first_name=str(request.data.get("name", "")).strip(),
        is_active=bool(request.data.get("is_active", True)),
        is_staff=bool(request.data.get("is_staff", False)),
    )
    return Response(serialize_user(user), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_detail(request, user_id):
    if not request.user.is_staff:
        return Response({"detail": "仅管理员可以管理用户"}, status=status.HTTP_403_FORBIDDEN)
    try:
        user = UserModel.objects.get(id=user_id)
    except UserModel.DoesNotExist:
        return Response({"detail": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        if user.id == request.user.id:
            return Response({"detail": "不能删除当前登录用户"}, status=status.HTTP_400_BAD_REQUEST)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    if "email" in request.data:
        user.email = str(request.data["email"]).strip()
    if "name" in request.data:
        user.first_name = str(request.data["name"]).strip()
    if "is_active" in request.data and user.id != request.user.id:
        user.is_active = bool(request.data["is_active"])
    if request.data.get("password"):
        if len(str(request.data["password"])) < 6:
            return Response({"detail": "密码至少 6 位"}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(str(request.data["password"]))
    user.save()
    if not user.is_active:
        Token.objects.filter(user=user).delete()
    return Response(serialize_user(user))


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
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
    return Response(serialize_account(account), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def account_detail(request, account_id):
    try:
        account = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        return Response({"detail": "账号不存在"}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        if account.file_configs.exists():
            return Response({"detail": "该账号已被文件管理配置引用，请先解除引用"}, status=status.HTTP_409_CONFLICT)
        account.delete()
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
    return Response(serialize_account(account))


def _get_account(account_id):
    try:
        return Account.objects.get(id=account_id)
    except Account.DoesNotExist as error:
        raise ValueError("关联账号不存在") from error


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
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
    return Response(serialize_file_config(config), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def file_config_detail(request, config_id):
    try:
        config = FileConfig.objects.select_related("account").get(id=config_id)
    except FileConfig.DoesNotExist:
        return Response({"detail": "文件管理配置不存在"}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        with transaction.atomic():
            current = FileConfig.objects.select_for_update().get(pk=config.pk)
            if 'revision' in request.data and request.data['revision'] != current.revision:
                return Response({'detail': '此记录已更新，请刷新后重试'}, status=409)
            current.delete()
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
def file_config_test_connection(request, config_id):
    try:
        config = FileConfig.objects.select_related("account").get(id=config_id)
    except FileConfig.DoesNotExist:
        return Response({"detail": "文件管理配置不存在"}, status=status.HTTP_404_NOT_FOUND)
    return _run_remote_action(config)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def file_config_refresh(request, config_id):
    try:
        config = FileConfig.objects.select_related("account").get(id=config_id)
    except FileConfig.DoesNotExist:
        return Response({"detail": "文件管理配置不存在"}, status=status.HTTP_404_NOT_FOUND)
    if not config.file_path.strip():
        return Response({"detail": "未配置文件路径，无法获取文件列表"}, status=status.HTTP_400_BAD_REQUEST)
    return _run_remote_action(config, refresh=True)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def file_lists(request):
    queryset = RemoteFile.objects.select_related("file_config")
    project = str(request.query_params.get("project", "")).strip()
    if project:
        queryset = queryset.filter(project__icontains=project)
    return Response([serialize_remote_file(item) for item in queryset])


@api_view(["GET", "PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
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
        attrs = write_remote_file(remote_file, content)
        remote_file.size = attrs.st_size
        remote_file.modified_at = timezone.make_aware(datetime.fromtimestamp(attrs.st_mtime)) if attrs.st_mtime else None
        remote_file.save(update_fields=["size", "modified_at", "fetched_at"])
        return Response({"detail": "文件保存成功", "file": serialize_remote_file(remote_file)})
    except Exception as error:
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def dashboard(request):
    now = timezone.localtime()
    labels = [(now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=11 - i)).strftime("%H:%M") for i in range(12)]
    return Response({
        "server": {
            "name": "config-hub-01",
            "address": "192.168.1.100",
            "os": "Ubuntu 24.04 LTS",
            "uptime": "12 天 8 小时",
            "status": "online",
        },
        "metrics": [
            {"key": "cpu", "label": "CPU 使用率", "value": 32, "unit": "%", "color": "#409eff", "trend": "+2.4%"},
            {"key": "memory", "label": "内存使用", "value": 6.8, "unit": " / 16 GB", "color": "#67c23a", "trend": "-0.8 GB"},
            {"key": "disk", "label": "磁盘空间", "value": 42, "unit": "%", "color": "#e6a23c", "trend": "128 / 500 GB"},
            {"key": "network", "label": "网络流量", "value": 18.6, "unit": " MB/s", "color": "#f56c6c", "trend": "↑ 12.4  ↓ 6.2"},
        ],
        "chart": {
            "labels": labels,
            "cpu": [22, 28, 25, 34, 31, 42, 36, 29, 33, 27, 35, 32],
            "memory": [41, 43, 42, 44, 43, 46, 45, 44, 43, 45, 44, 43],
        },
        "services": [
            {"name": "Nginx", "description": "Web 服务器", "status": "运行中", "version": "1.26.2", "icon": "Connection", "color": "#e8f4ff"},
            {"name": "MySQL", "description": "关系型数据库", "status": "运行中", "version": "8.0.40", "icon": "Coin", "color": "#fff3e0"},
            {"name": "Docker", "description": "容器引擎", "status": "运行中", "version": "27.3.1", "icon": "Box", "color": "#e8f7ef"},
            {"name": "Redis", "description": "缓存服务", "status": "运行中", "version": "7.4.1", "icon": "Grid", "color": "#fdecec"},
        ],
        "activity": [
            {"title": "系统服务启动完成", "detail": "Nginx 服务已启动", "time": "10:42:18", "type": "success"},
            {"title": "配置文件已更新", "detail": "nginx.conf 配置已保存", "time": "09:36:05", "type": "primary"},
            {"title": "系统安全检查", "detail": "未发现风险项", "time": "08:15:32", "type": "success"},
        ],
    })
