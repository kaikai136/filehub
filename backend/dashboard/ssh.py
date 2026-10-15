from datetime import datetime
from io import StringIO
import posixpath
import stat
from uuid import uuid4

import paramiko
from django.utils import timezone

from .security import decrypt_value


MAX_REMOTE_TEXT_BYTES = 2 * 1024 * 1024


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


def _remote_path(remote_file):
    base_path = remote_file.file_config.file_path.rstrip("/") or "/"
    relative_path = remote_file.relative_path
    path = posixpath.normpath(relative_path if relative_path.startswith("/") else posixpath.join(base_path, relative_path))
    if not relative_path.startswith("/") and base_path != "/" and path != base_path and not path.startswith(base_path + "/"):
        raise ValueError("文件路径超出配置目录")
    return path


def read_remote_file(remote_file, client=None):
    client = client if client is not None else connect(remote_file.file_config)
    sftp = None
    try:
        sftp = client.open_sftp()
        path = _remote_path(remote_file)
        attrs = sftp.stat(path)
        if attrs.st_size > MAX_REMOTE_TEXT_BYTES:
            raise ValueError("文件超过 2 MB，暂不支持在线编辑")
        with sftp.file(path, "rb") as handle:
            data = handle.read(MAX_REMOTE_TEXT_BYTES + 1)
        if len(data) > MAX_REMOTE_TEXT_BYTES:
            raise ValueError("文件超过 2 MB，暂不支持在线编辑")
        if b"\x00" in data:
            raise ValueError("该文件可能是二进制文件，无法在线编辑")
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("文件不是 UTF-8 编码，暂不支持在线编辑") from error
    finally:
        try:
            if sftp is not None:
                sftp.close()
        finally:
            client.close()


def write_remote_file(remote_file, content, client=None):
    data = content.encode("utf-8")
    if len(data) > MAX_REMOTE_TEXT_BYTES:
        raise ValueError("文件超过 2 MB，暂不支持在线编辑")
    client = client if client is not None else connect(remote_file.file_config)
    sftp = None
    temp_path = None
    try:
        sftp = client.open_sftp()
        path = _remote_path(remote_file)
        attrs = sftp.stat(path)
        temp_path = f"{path}.confighub-{uuid4().hex}.tmp"
        with sftp.file(temp_path, "wb") as handle:
            handle.write(data)
            handle.flush()
        sftp.chmod(temp_path, stat.S_IMODE(attrs.st_mode))
        if hasattr(sftp, "posix_rename"):
            sftp.posix_rename(temp_path, path)
        else:
            sftp.remove(path)
            sftp.rename(temp_path, path)
        temp_path = None
        return sftp.stat(path)
    finally:
        if sftp is not None and temp_path is not None:
            try:
                sftp.remove(temp_path)
            except Exception:
                pass
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
