import posixpath
import re
import shlex
import unicodedata


BLOCKED_COMMAND_GROUPS = {
    "删除与破坏": "rm unlink rmdir shred truncate",
    "磁盘与文件系统": "dd mkfs mke2fs wipefs fdisk sfdisk cfdisk parted sgdisk gdisk blkdiscard mount umount fsck",
    "系统与进程控制": "shutdown reboot poweroff halt init telinit systemctl service kill pkill killall chmod chown chgrp chattr passwd useradd usermod userdel groupadd groupmod groupdel crontab",
    "间接执行": "sudo su doas env command exec eval source . sh bash dash zsh ksh ash fish busybox xargs find awk gawk mawk sed vi vim nvim ex ssh sftp scp kubectl docker podman nsenter chroot nohup setsid timeout watch parallel make",
    "脚本解释器": "python python2 python3 perl ruby node nodejs php lua luajit",
}
BLOCKED_COMMANDS = {
    command: reason
    for reason, commands in BLOCKED_COMMAND_GROUPS.items()
    for command in commands.split()
}
RESERVED_WORDS = frozenset("if then else elif fi for while until do done case esac in function select time coproc !".split())


def _segments(command):
    segments = []
    current = []
    quote = None
    position = 0
    pending_operator = None
    while position < len(command):
        character = command[position]
        if unicodedata.category(character) in {"Cc", "Cf"} and character not in "\n\t":
            raise ValueError("不允许控制字符")
        if character == "\\" and quote != "'":
            if position + 1 >= len(command) or command[position + 1] == "\n":
                raise ValueError("不允许不完整转义或续行语法")
            escaped = command[position + 1]
            if unicodedata.category(escaped) in {"Cc", "Cf"}:
                raise ValueError("不允许转义控制字符")
            current.extend([character, escaped])
            position += 2
            continue
        if character in {"$", "`"} and quote != "'":
            raise ValueError("不允许变量、命令替换或反引号")
        if quote:
            current.append(character)
            if character == quote:
                quote = None
        elif character in {"'", '"'}:
            quote = character
            current.append(character)
        elif character in "<>(){}!#":
            raise ValueError("不允许重定向、分组、流程控制或注释语法")
        elif character in ";|&\n":
            operator = character
            if character in "|&" and position + 1 < len(command) and command[position + 1] == character:
                operator += character
                position += 1
            if operator == "&":
                raise ValueError("不允许后台执行")
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
                current = []
            elif operator != "\n":
                raise ValueError("命令连接语法无效")
            if operator != "\n" or segment:
                pending_operator = operator
        else:
            current.append(character)
        position += 1
    if quote:
        raise ValueError("命令引号未闭合")
    segment = "".join(current).strip()
    if segment:
        segments.append(segment)
    elif pending_operator in {"|", "||", "&&"}:
        raise ValueError("命令连接语法不完整")
    if not segments:
        raise ValueError("命令内容不能为空")
    return segments


def shell_command_error(command, rules=None):
    try:
        for segment in _segments(command):
            tokens = shlex.split(segment, comments=False, posix=True)
            if not tokens or not tokens[0]:
                raise ValueError("命令名称不能为空")
            executable = tokens[0]
            if executable.startswith(("./", "../", "~/")):
                raise ValueError("不允许执行相对路径或用户目录中的自定义程序")
            if any(character in executable for character in "=*?[]~"):
                raise ValueError("不允许环境赋值或动态命令名称")
            name = posixpath.basename(executable)
            if name in RESERVED_WORDS:
                raise ValueError("不允许流程控制或函数语法")
            reason = None
            if rules is None:
                reason = BLOCKED_COMMANDS.get(name)
                if name.startswith(("mkfs.", "fsck.")):
                    reason = "磁盘与文件系统"
                if re.fullmatch(r"python(?:[0-9]+(?:[.][0-9]+)*)?", name):
                    reason = "脚本解释器"
            else:
                for rule in rules:
                    if not rule["enabled"]:
                        continue
                    if rule["match"] == "exact":
                        matches = name == rule["command"]
                    elif rule["match"] == "prefix":
                        matches = name.startswith(rule["command"])
                    else:
                        matches = bool(re.fullmatch(r"python(?:[0-9]+(?:[.][0-9]+)*)?", name))
                    if matches:
                        reason = rule["category"]
                        break
            if reason:
                raise ValueError(f"禁止执行 {name}（{reason}）")
    except ValueError as error:
        return f"Shell 安全拦截：{error}"
    return None
