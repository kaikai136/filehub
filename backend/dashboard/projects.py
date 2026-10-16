from ipaddress import ip_address

from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError

from .models import FileConfig, Project, RemoteFile


def project_payload(project):
    return {'id': project.id, 'name': project.name, 'parent_id': project.parent_id,
            'sort_order': project.sort_order, 'path': project.path}


def resolve_project(data, current=None):
    if 'project_id' in data:
        try:
            return Project.objects.get(pk=int(data['project_id']))
        except (Project.DoesNotExist, ValueError, TypeError):
            raise ValidationError('请选择有效项目')
    if 'project' in data:
        name = str(data['project']).strip()
        if not name or len(name) > 150:
            raise ValidationError('项目名称不能为空且不能超过 150 字符')
        # Legacy clients refer to top-level projects by name.
        return Project.objects.get_or_create(name=name, parent=None)[0]
    if current:
        return current.project_node
    raise ValidationError('请选择项目')


def validate_config(data, current=None):
    for field in ('host_name', 'ip_address'):
        value = str(data.get(field, getattr(current, field, ''))).strip()
        if not value or len(value) > 150:
            raise ValidationError(f'{field} 不能为空或超出长度限制')
    # These values are populated by inspection or retained for legacy file-management
    # clients.  Project host records may be created before inspection and without a
    # remote file directory.
    for field, limit in (('machine_name', 150), ('file_path', 500)):
        if field in data and len(str(data.get(field) or '').strip()) > limit:
            raise ValidationError(f'{field} 超出长度限制')
    try:
        address = ip_address(str(data.get('ip_address', getattr(current, 'ip_address', ''))).strip())
        if address.version != 4:
            raise ValueError()
        port = int(data.get('port', getattr(current, 'port', 22)))
        if not 1 <= port <= 65535:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValidationError('IP 地址或端口无效')


@transaction.atomic
def save_project(data, project_id=None):
    # Lock the tree during parent changes and associated legacy-label updates.
    nodes = {p.id: p for p in Project.objects.select_for_update().all()}
    if project_id is not None and project_id not in nodes:
        raise ValidationError('项目不存在')
    node = nodes.get(project_id) or Project()
    name = str(data.get('name', node.name)).strip()
    if not name or len(name) > 150 or '/' in name or '\\' in name:
        raise ValidationError('项目名称不能为空、不能超过 150 字符或包含路径分隔符')
    try:
        parent_id = data.get('parent_id', node.parent_id)
        parent_id = int(parent_id) if parent_id is not None else None
        order = int(data.get('sort_order', node.sort_order))
    except (ValueError, TypeError):
        raise ValidationError('父项目或排序值无效')
    if order < 0 or (parent_id is not None and parent_id not in nodes):
        raise ValidationError('父项目或排序值无效')
    cursor = parent_id
    while cursor is not None:
        if cursor == node.pk:
            raise ValidationError('不能移动到自身或子项目中')
        cursor = nodes[cursor].parent_id
    if Project.objects.filter(parent_id=parent_id, name=name).exclude(pk=node.pk).exists():
        raise ValidationError('同级项目名称已存在')
    node.name, node.parent_id, node.sort_order = name, parent_id, order
    node.save()
    configs = FileConfig.objects.filter(project_node=node)
    configs.exclude(project=name).update(project=name, revision=F('revision') + 1)
    RemoteFile.objects.filter(file_config__project_node=node).update(project=name)
    return node
