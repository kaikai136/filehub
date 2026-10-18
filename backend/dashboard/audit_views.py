from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from datetime import datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from .authentication import ExpiryTokenAuthentication as TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import FileAudit, OperationAudit
from .audit import purge_expired_audits
from .rbac import require_permission


def _operator(record):
    return {
        'id': record.operator_id,
        'username': record.operator_username,
        'name': record.operator_name or record.operator_username or '系统',
    }


def _pagination(request, queryset, serializer):
    try:
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
    except (TypeError, ValueError):
        raise ValidationError('分页参数无效')
    paginator = Paginator(queryset, page_size)
    try:
        items = paginator.page(page)
    except EmptyPage:
        items = []
    return Response({
        'count': paginator.count, 'page': page, 'page_size': page_size,
        'results': [serializer(item) for item in items],
    })


def _date_filter(request, queryset, field):
    for key, lookup in [('start_time', 'gte'), ('end_time', 'lte')]:
        value = request.query_params.get(key)
        if not value:
            continue
        parsed = parse_datetime(value)
        if parsed is None:
            date = parse_date(value)
            if date is None:
                raise ValidationError(f'{key} 格式无效')
            parsed = datetime.combine(date, time.min if key == 'start_time' else time.max)
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        queryset = queryset.filter(**{f'{field}__{lookup}': parsed})
    return queryset


def serialize_file_audit(record, include_diff=False):
    data = {
        'id': record.id, 'project_name': record.project_name, 'project_id': record.project_id,
        'ip_address': record.ip_address, 'directory': record.directory,
        'relative_path': record.relative_path, 'operator': _operator(record),
        'changed_at': record.changed_at.isoformat(),
    }
    if include_diff:
        data['diff'] = record.diff
    return data


def serialize_operation_audit(record):
    return {
        'id': record.id, 'occurred_at': record.occurred_at.isoformat(),
        'operator': _operator(record), 'module': record.module, 'action': record.action,
        'object': record.object_name, 'ip_address': record.ip_address, 'detail': record.detail,
    }


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission('file_audit.view')
def file_audits(request):
    purge_expired_audits()
    queryset = FileAudit.objects.select_related('operator')
    queryset = _date_filter(request, queryset, 'changed_at')
    for parameter, field in [('project', 'project_name'), ('ip', 'ip_address'), ('directory', 'directory')]:
        value = request.query_params.get(parameter, '').strip()
        if value:
            queryset = queryset.filter(**{f'{field}__icontains': value})
    operator = request.query_params.get('operator', '').strip()
    if operator:
        queryset = queryset.filter(Q(operator_name__icontains=operator) | Q(operator_username__icontains=operator))
    keyword = request.query_params.get('keyword', '').strip()
    if keyword:
        queryset = queryset.filter(Q(project_name__icontains=keyword) | Q(directory__icontains=keyword) | Q(ip_address__icontains=keyword))
    return _pagination(request, queryset, serialize_file_audit)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission('file_audit.view')
def file_audit_detail(request, audit_id):
    try:
        record = FileAudit.objects.select_related('operator').get(pk=audit_id)
    except FileAudit.DoesNotExist:
        return Response({'detail': '文件审计记录不存在'}, status=404)
    return Response(serialize_file_audit(record, include_diff=True))


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@require_permission('operation_audit.view')
def operation_audits(request):
    purge_expired_audits()
    queryset = OperationAudit.objects.select_related('operator')
    queryset = _date_filter(request, queryset, 'occurred_at')
    for parameter, field in [('module', 'module'), ('action', 'action'), ('ip', 'ip_address')]:
        value = request.query_params.get(parameter, '').strip()
        if value:
            queryset = queryset.filter(**{f'{field}__icontains': value})
    operator = request.query_params.get('operator', '').strip()
    if operator:
        queryset = queryset.filter(Q(operator_name__icontains=operator) | Q(operator_username__icontains=operator))
    keyword = request.query_params.get('keyword', '').strip()
    if keyword:
        queryset = queryset.filter(Q(object_name__icontains=keyword) | Q(detail__icontains=keyword))
    return _pagination(request, queryset, serialize_operation_audit)
