from types import SimpleNamespace

from django.conf import settings
from django.db import models


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="角色名称")
    code = models.CharField(max_length=100, unique=True, verbose_name="角色标识")
    is_active = models.BooleanField(default=True, verbose_name="启用状态")
    permissions = models.JSONField(default=list, verbose_name="权限标识")
    is_builtin = models.BooleanField(default=False, editable=False, verbose_name="内置角色")
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="roles", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class FileAudit(models.Model):
    project_name = models.CharField(max_length=255, verbose_name="项目名")
    project_id = models.BigIntegerField(null=True, blank=True, verbose_name="项目 ID")
    ip_address = models.GenericIPAddressField(verbose_name="IP 地址")
    directory = models.CharField(max_length=500, verbose_name="文件目录")
    relative_path = models.CharField(max_length=500, verbose_name="文件相对路径")
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="file_audits")
    operator_name = models.CharField(max_length=255, blank=True, default="")
    operator_username = models.CharField(max_length=150, blank=True, default="")
    changed_at = models.DateTimeField(auto_now_add=True, verbose_name="更改时间")
    diff = models.TextField(verbose_name="变更内容")
    file_config = models.ForeignKey("FileConfig", null=True, blank=True, on_delete=models.SET_NULL, related_name="file_audits")
    remote_file = models.ForeignKey("RemoteFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="audits")

    class Meta:
        ordering = ["-changed_at", "-id"]
        indexes = [
            models.Index(fields=["-changed_at"], name="file_audit_time_idx"),
            models.Index(fields=["ip_address", "-changed_at"], name="file_audit_ip_time_idx"),
            models.Index(fields=["project_id", "-changed_at"], name="file_audit_project_idx"),
        ]


class OperationAudit(models.Model):
    occurred_at = models.DateTimeField(auto_now_add=True, verbose_name="时间")
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="operation_audits")
    operator_name = models.CharField(max_length=255, blank=True, default="")
    operator_username = models.CharField(max_length=150, blank=True, default="")
    module = models.CharField(max_length=80, verbose_name="模块")
    action = models.CharField(max_length=80, verbose_name="操作")
    object_name = models.CharField(max_length=255, blank=True, default="", verbose_name="对象")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    detail = models.TextField(blank=True, default="", verbose_name="详情")

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["-occurred_at"], name="operation_audit_time_idx"),
            models.Index(fields=["module", "-occurred_at"], name="operation_audit_module_idx"),
            models.Index(fields=["ip_address", "-occurred_at"], name="operation_audit_ip_idx"),
        ]


class Account(models.Model):
    name = models.CharField(max_length=100, verbose_name="账号名称")
    username = models.CharField(max_length=150, verbose_name="用户")
    encrypted_password = models.TextField(blank=True, default="", verbose_name="加密密码")
    encrypted_private_key = models.TextField(blank=True, default="", verbose_name="加密私钥")
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="备注")
    is_active = models.BooleanField(default=True, verbose_name="启用状态")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Project(models.Model):
    name = models.CharField(max_length=150)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['parent', 'name'], name='project_sibling_name'),
            models.UniqueConstraint(fields=['name'], condition=models.Q(parent__isnull=True), name='project_root_name'),
        ]

    @property
    def path(self):
        parts, node = [], self
        while node:
            parts.append(node.name)
            node = node.parent
        return '/'.join(reversed(parts))


class FileConfig(models.Model):
    project_node = models.ForeignKey(Project, null=True, blank=True, on_delete=models.PROTECT, related_name='configs')
    project = models.CharField(max_length=150, verbose_name="项目")
    host_name = models.CharField(max_length=150, verbose_name="主机名称")
    ip_address = models.GenericIPAddressField(verbose_name="IP 地址")
    machine_name = models.CharField(max_length=150, blank=True, default="", verbose_name="机器名称")
    port = models.PositiveIntegerField(default=22, verbose_name="SSH 端口")
    file_path = models.CharField(max_length=500, blank=True, default="", verbose_name="文件路径")
    directory_paths = models.JSONField(default=list, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="file_configs")
    account_snapshot = models.JSONField(default=dict, editable=False)
    revision = models.PositiveBigIntegerField(default=0, editable=False)
    specifications = models.JSONField(default=dict, editable=False)
    platform_type = models.CharField(max_length=20, default='', blank=True)
    inspection_status = models.CharField(max_length=20, default='pending')
    inspection_error = models.TextField(default='', blank=True)
    last_inspected_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default="pending")
    connection_status = models.CharField(max_length=20, default="pending")
    connection_error = models.TextField(blank=True, default="")
    last_verified_at = models.DateTimeField(null=True, blank=True)
    fetch_status = models.CharField(max_length=20, default="pending")
    fetch_error = models.TextField(blank=True, default="")
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.project

    def bind_account(self, account):
        self.account = account
        self.account_snapshot = {
            field: getattr(account, field)
            for field in (
                "name", "username", "encrypted_password", "encrypted_private_key", "is_active",
            )
        }

    @property
    def ssh_account(self):
        return SimpleNamespace(**self.account_snapshot)

    def save(self, *args, **kwargs):
        if not self.project_node_id:
            self.project_node, _ = Project.objects.get_or_create(name=self.project, parent=None)
            if kwargs.get('update_fields'):
                kwargs['update_fields'] = [*kwargs['update_fields'], 'project_node']
        self.project = self.project_node.name
        if not self.account_snapshot:
            self.bind_account(self.account)
        super().save(*args, **kwargs)


class RemoteFile(models.Model):
    file_config = models.ForeignKey(FileConfig, on_delete=models.CASCADE, related_name="remote_files")
    project = models.CharField(max_length=150)
    name = models.CharField(max_length=255)
    relative_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=20, default="file")
    size = models.BigIntegerField(default=0)
    modified_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["relative_path"]

