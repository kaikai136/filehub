from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from .authentication import ExpiryTokenAuthentication as TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import FileConfig, Project
from .projects import project_payload, save_project
from .inspection import inspect_machine
from .ssh import connect
from .views import serialize_file_config, _store_remote_result, _stale_action_response
from .rbac import require_method_permissions, require_permission
from .audit import record_operation_audit
from .notifications import config_snapshot, record_config_notification


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_method_permissions({'GET': ('projects.view', 'file_configs.view', 'file_lists.view'), 'POST': 'projects.create'})
def projects(request):
    if request.method == 'GET':
        return Response([project_payload(p) for p in Project.objects.select_related('parent')])
    try:
        result = save_project(request.data)
        record_operation_audit(request, '项目管理', '新增', result.name, '创建项目')
        return Response(project_payload(result), status=201)
    except IntegrityError:
        raise ValidationError('同级项目名称已存在')


@api_view(['PATCH', 'DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_method_permissions({'PATCH': 'projects.edit', 'DELETE': 'projects.delete'})
def project_detail(request, project_id):
    node = get_object_or_404(Project, pk=project_id)
    if request.method == 'DELETE':
        try:
            object_name = node.path
            node.delete()
            record_operation_audit(request, '项目管理', '删除', object_name, '删除项目')
        except ProtectedError:
            return Response({'detail': '项目包含子项目或主机配置，请先移走后再删除'}, status=400)
        return Response(status=204)
    try:
        result = save_project(request.data, project_id)
        record_operation_audit(request, '项目管理', '编辑', result.name, '更新项目')
        return Response(project_payload(result))
    except IntegrityError:
        raise ValidationError('同级项目名称已存在')


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission('projects.execute')
def inspect_config(request, config_id):
    config = get_object_or_404(FileConfig, pk=config_id)
    if not FileConfig.objects.filter(pk=config.pk, revision=config.revision).update(revision=F('revision') + 1):
        return _stale_action_response(config)
    config.revision += 1
    try:
        client = connect(config)
    except Exception as error:
        config.connection_status, config.connection_error = 'error', str(error)
        config.inspection_status, config.inspection_error = 'error', str(error)
        if not _store_remote_result(config, ['connection_status', 'connection_error', 'inspection_status', 'inspection_error']):
            return _stale_action_response(config)
        return Response({'detail': str(error), 'config': serialize_file_config(config)}, status=400)
    try:
        config.connection_status, config.connection_error = 'success', ''
        config.last_verified_at = timezone.now()
        fields = ['connection_status', 'connection_error', 'last_verified_at', 'inspection_status', 'inspection_error']
        try:
            result = inspect_machine(client)
            config.machine_name = str(result.pop('machine_name'))[:150]
            config.platform_type = result.pop('platform_type')
            config.specifications = result
            config.inspection_status, config.inspection_error = 'success', ''
            config.last_inspected_at = timezone.now()
            fields += ['machine_name', 'platform_type', 'specifications', 'last_inspected_at']
        except Exception as error:
            config.inspection_status, config.inspection_error = 'error', str(error)
        if not _store_remote_result(config, fields):
            return _stale_action_response(config)
        record_operation_audit(request, '项目管理', '执行', config.host_name, '验证 SSH 并采集机器规格')
        return Response({'detail': 'SSH 验证成功' if config.inspection_error else '验证与规格采集成功', 'config': serialize_file_config(config)})
    finally:
        client.close()


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def batch_configs(request):
    action, items = request.data.get('action'), request.data.get('items')
    from .permissions import has_permission
    required = 'projects.delete' if action == 'delete' else 'projects.edit'
    if not has_permission(request.user, required):
        return Response({'detail': '没有执行此操作的权限'}, status=403)
    if action not in ('move', 'delete') or not isinstance(items, list) or not items:
        raise ValidationError('请选择操作和主机')
    if action == 'move':
        try:
            project = Project.objects.get(pk=int(request.data.get('project_id')))
        except (Project.DoesNotExist, ValueError, TypeError):
            raise ValidationError('请选择有效目标项目')
    else:
        project = None
    results = []
    notification_events = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), int) or not isinstance(item.get('revision'), int):
            raise ValidationError('主机 ID 与版本不能为空')
    for item in items:
        with transaction.atomic():
            config = FileConfig.objects.select_for_update().filter(pk=item['id']).first()
            if config is None or config.revision != item['revision']:
                results.append({'id': item['id'], 'success': False, 'error': '记录不存在或已更新，请刷新'})
                continue
            if action == 'delete':
                if config.host_config_id is None and config.path_configs.exists():
                    results.append({'id': item['id'], 'success': False, 'error': '该机器已关联文件管理记录，请先删除文件管理记录后再删除机器'})
                    continue
                snapshot = config_snapshot(config)
                config.delete()
                notification_events.append(('deleted', None, snapshot))
            else:
                config.project_node, config.project = project, project.name
                config.revision += 1
                config.save(update_fields=['project_node', 'project', 'revision', 'updated_at'])
                config.remote_files.update(project=project.name)
                notification_events.append(('updated', config, None))
            results.append({'id': item['id'], 'success': True})
    record_operation_audit(request, '项目管理', '批量操作', '文件配置', f'批量{action} {len(items)} 条')
    for event_type, config, snapshot in notification_events:
        record_config_notification(request, event_type, config=config, snapshot=snapshot)
    return Response({'results': results})
