from types import SimpleNamespace

from django.db import models


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


class FileConfig(models.Model):
    project = models.CharField(max_length=150, verbose_name="项目")
    host_name = models.CharField(max_length=150, verbose_name="主机名称")
    ip_address = models.GenericIPAddressField(verbose_name="IP 地址")
    machine_name = models.CharField(max_length=150, verbose_name="机器名称")
    port = models.PositiveIntegerField(default=22, verbose_name="SSH 端口")
    file_path = models.CharField(max_length=500, verbose_name="文件路径")
    directory_paths = models.JSONField(default=list, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="file_configs")
    account_snapshot = models.JSONField(default=dict, editable=False)
    revision = models.PositiveBigIntegerField(default=0, editable=False)
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

