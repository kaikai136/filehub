import difflib
import logging
import posixpath
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import FileAudit, OperationAudit, SystemSetting


logger = logging.getLogger(__name__)


def purge_expired_audits(now=None):
    setting, _ = SystemSetting.objects.get_or_create(pk=1)
    current_time = now or timezone.now()
    file_deleted, _ = FileAudit.objects.filter(
        changed_at__lt=current_time - timedelta(days=setting.file_audit_retention_days),
    ).delete()
    operation_deleted, _ = OperationAudit.objects.filter(
        occurred_at__lt=current_time - timedelta(days=setting.operation_audit_retention_days),
    ).delete()
    return {"file_audits": file_deleted, "operation_audits": operation_deleted}


def _operator_values(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return {'operator': None, 'operator_name': '系统', 'operator_username': ''}
    return {
        'operator': user,
        'operator_name': user.get_full_name() or user.username,
        'operator_username': user.username,
    }


def client_ip(request):
    return request.META.get('REMOTE_ADDR') or None


def _safely_create(model, **values):
    try:
        with transaction.atomic():
            return model.objects.create(**values)
    except Exception:
        logger.exception('Failed to persist %s', model.__name__)
        return None


def record_operation_audit(request, module, action, object_name='', detail='', user=None):
    _safely_create(
        OperationAudit,
        **_operator_values(user or getattr(request, 'user', None)),
        module=str(module)[:80], action=str(action)[:80], object_name=str(object_name)[:255],
        ip_address=client_ip(request), detail=str(detail),
    )


def unified_diff(before, after, path):
    lines = list(difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile=f'{path} (修改前)', tofile=f'{path} (修改后)', n=3, lineterm='',
    ))
    return '\n'.join(lines) + ('\n' if lines else '')


def remote_file_path(remote_file):
    config = remote_file.file_config
    return remote_file.relative_path if remote_file.relative_path.startswith('/') else posixpath.join(config.file_path, remote_file.relative_path)


def record_file_audit(request, remote_file, before, after):
    config = remote_file.file_config
    path = remote_file_path(remote_file)
    difference = unified_diff(before, after, path)
    if not difference:
        return None
    values = {
        **_operator_values(getattr(request, 'user', None)),
        'project_name': config.project_node.path if config.project_node_id else config.project,
        'project_id': config.project_node_id,
        'ip_address': config.ip_address,
        'directory': path,
        'relative_path': remote_file.relative_path,
        'diff': difference,
        'file_config': config,
        'remote_file': remote_file,
    }
    return _safely_create(FileAudit, **values)
