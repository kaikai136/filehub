from types import SimpleNamespace

from django.conf import settings
from django.db import models


class CommandPolicy(models.Model):
    rules = models.JSONField(default=list)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


class UserTwoFactor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="two_factor")
    enabled = models.BooleanField(default=False)
    required = models.BooleanField(default=False)
    encrypted_secret = models.TextField(blank=True, default="")
    bound_at = models.DateTimeField(null=True, blank=True)
    last_step = models.BigIntegerField(default=-1)


class AuthChallenge(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    kind = models.CharField(max_length=20)
    payload = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)


class LoginSession(models.Model):
    token = models.OneToOneField("authtoken.Token", on_delete=models.CASCADE, related_name="login_session", primary_key=True)
    expires_at = models.DateTimeField()


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


class ConfigNotification(models.Model):
    EVENT_CHOICES = [
        ("created", "新增"),
        ("updated", "编辑"),
        ("deleted", "删除"),
    ]

    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="config_notifications",
    )
    operator_name = models.CharField(max_length=255, blank=True, default="")
    operator_username = models.CharField(max_length=150, blank=True, default="")
    project_name = models.CharField(max_length=500, blank=True, default="")
    host_name = models.CharField(max_length=150, blank=True, default="")
    ip_address = models.GenericIPAddressField()
    path = models.CharField(max_length=500, blank=True, default="")
    previous_path = models.CharField(max_length=500, blank=True, default="")
    file_config = models.ForeignKey(
        "FileConfig", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="notifications",
    )
    file_audit = models.OneToOneField(
        FileAudit, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="config_notification",
    )
    file_config_id_snapshot = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["-created_at"], name="config_notice_time_idx")]


class ConfigNotificationRead(models.Model):
    notification = models.ForeignKey(ConfigNotification, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="config_notification_reads")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notification", "user"], name="unique_config_notification_read"),
        ]


class CommandExecution(models.Model):
    MODE_CHOICES = [("shell", "Shell"), ("k8s", "K8s")]
    STATUS_CHOICES = [
        ("queued", "排队中"),
        ("running", "执行中"),
        ("succeeded", "成功"),
        ("failed", "失败"),
        ("stopped", "已停止"),
        ("timeout", "超时"),
    ]

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="command_executions",
    )
    operator_name = models.CharField(max_length=255, blank=True, default="")
    operator_username = models.CharField(max_length=150, blank=True, default="")
    file_config = models.ForeignKey(
        "FileConfig", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="command_executions",
    )
    project_name = models.CharField(max_length=500, blank=True, default="")
    host_name = models.CharField(max_length=150, blank=True, default="")
    ip_address = models.GenericIPAddressField()
    port = models.PositiveIntegerField(default=22)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    working_directory = models.CharField(max_length=500, default="/root")
    remote_file = models.ForeignKey(
        "RemoteFile", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="command_executions",
    )
    file_path = models.CharField(max_length=1000, blank=True, default="")
    command = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    exit_code = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    output_truncated = models.BooleanField(default=False)
    stop_requested = models.BooleanField(default=False)
    requested_ip = models.GenericIPAddressField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["-created_at"], name="command_exec_time_idx"),
            models.Index(fields=["status", "-created_at"], name="command_exec_status_idx"),
            models.Index(fields=["operator", "-created_at"], name="command_exec_user_idx"),
        ]


class CommandExecutionOutput(models.Model):
    STREAM_CHOICES = [("stdout", "stdout"), ("stderr", "stderr")]

    execution = models.ForeignKey(CommandExecution, on_delete=models.CASCADE, related_name="outputs")
    stream = models.CharField(max_length=10, choices=STREAM_CHOICES)
    sequence = models.PositiveIntegerField()
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(fields=["execution", "sequence"], name="unique_command_output_sequence"),
        ]


class SystemSetting(models.Model):
    """The single persisted set of console-wide preferences."""
    WATERMARK_MODES = [("username", "登录用户名"), ("custom", "自定义文字")]

    font_size = models.PositiveSmallIntegerField(default=16)
    watermark_enabled = models.BooleanField(default=False)
    watermark_mode = models.CharField(max_length=20, choices=WATERMARK_MODES, default="username")
    watermark_text = models.CharField(max_length=120, default="FileHub", blank=True)
    watermark_opacity = models.PositiveSmallIntegerField(default=12)
    watermark_rotation = models.SmallIntegerField(default=-20)
    file_audit_retention_days = models.PositiveIntegerField(default=180)
    operation_audit_retention_days = models.PositiveIntegerField(default=180)
    login_expiry_minutes = models.PositiveIntegerField(default=480)
    github_url = models.URLField(default="https://github.com/", max_length=500)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_system_settings")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "系统设置"


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
    host_config = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE,
        related_name='path_configs', editable=False,
    )
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
