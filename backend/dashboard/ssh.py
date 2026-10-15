from datetime import datetime
from io import StringIO
import posixpath
import stat

import paramiko
from django.utils import timezone

from .security import decrypt_value


def connect(file_config):
    account = file_config.ssh_account
    if not account.is_active:
        raise ValueError("关联账号已禁用")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs = {
        "hostname": file_config.ip_address,
        "port": file_config.port,
        "username": account.username,
        "timeout": 10,
        "banner_timeout": 10,
        "auth_timeout": 10,
        "allow_agent": False,
        "look_for_keys": False,
    }
    private_key = decrypt_value(account.encrypted_private_key)
    password = decrypt_value(account.encrypted_password)
    if private_key:
        key_error = None
        key_types = [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]
        if hasattr(paramiko, "DSSKey"):
            key_types.append(paramiko.DSSKey)
        for key_type in key_types:
            try:
                kwargs["pkey"] = key_type.from_private_key(StringIO(private_key))
                break
            except (paramiko.SSHException, ValueError) as error:
                key_error = error
        if "pkey" not in kwargs:
            raise ValueError(f"SSH 私钥格式无效: {key_error}")
    elif password:
        kwargs["password"] = password
    else:
        raise ValueError("账号未配置密码或独立密钥")
    try:
        client.connect(**kwargs)
        transport = client.get_transport()
        if not transport or not transport.is_active() or not transport.is_authenticated():
            raise ConnectionError("SSH 登录验证失败")
    except Exception:
        client.close()
        raise
    return client


def _file_info(file_config, base_path, relative_path, attrs):
    mode = attrs.st_mode
    file_type = "directory" if stat.S_ISDIR(mode) else "file"
    return {
        "project": file_config.project,
        "name": posixpath.basename(relative_path.rstrip("/")) or relative_path,
        "relative_path": relative_path,
        "file_type": file_type,
        "size": 0 if file_type == "directory" else attrs.st_size,
        "modified_at": timezone.make_aware(datetime.fromtimestamp(attrs.st_mtime)) if attrs.st_mtime else None,
    }


class RemoteListing(list):
    def __init__(self):
        super().__init__()
        self.directory_paths = []


def list_remote_files(file_config, client=None):
    client = client if client is not None else connect(file_config)
    sftp = None
    try:
        sftp = client.open_sftp()
        root = file_config.file_path.rstrip("/") or "/"
        try:
            root_attrs = sftp.stat(root)
        except FileNotFoundError as error:
            raise FileNotFoundError(f"远程路径不存在: {root}") from error
        if not stat.S_ISDIR(root_attrs.st_mode):
            return [_file_info(file_config, root, root, root_attrs)]
        results = RemoteListing()
        for current_path, directories, filenames in _walk(sftp, root):
            results.directory_paths.extend(
                posixpath.relpath(posixpath.join(current_path, name), root) for name in directories
            )
            for name, attrs in filenames:
                relative = posixpath.relpath(posixpath.join(current_path, name), root)
                results.append(_file_info(file_config, root, relative, attrs))
        return results
    finally:
        try:
            if sftp is not None:
                sftp.close()
        finally:
            client.close()


def _walk(sftp, root):
    pending = [root]
    while pending:
        current = pending.pop()
        directories = []
        files = []
        for entry in sftp.listdir_attr(current):
            path = posixpath.join(current, entry.filename)
            if stat.S_ISDIR(entry.st_mode):
                directories.append(entry.filename)
                pending.append(path)
            else:
                files.append((entry.filename, entry))
        yield current, directories, files


def test_connection(file_config):
    client = connect(file_config)
    client.close()
