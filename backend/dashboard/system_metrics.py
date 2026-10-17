from collections import deque
from datetime import datetime
import platform
import socket
import threading
import time

import psutil
from django.conf import settings
from django.utils import timezone


_history = deque(maxlen=90)
_history_lock = threading.Lock()
_network_lock = threading.Lock()
_last_network_sample = None


def _format_bytes(value):
    value = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            digits = 0 if value >= 100 or unit == "B" else 1
            return f"{value:.{digits}f} {unit}"
        value /= 1024


def _format_uptime(seconds):
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f"{days} 天 {hours} 小时"
    if hours:
        return f"{hours} 小时 {minutes} 分钟"
    return f"{minutes} 分钟"


def _host_address():
    try:
        addresses = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        values = [item[4][0] for item in addresses]
        return next((value for value in values if not value.startswith("127.")), values[0])
    except (OSError, IndexError):
        return "127.0.0.1"


def _network_rates():
    global _last_network_sample
    counters = psutil.net_io_counters()
    now = time.monotonic()
    sent_rate = received_rate = 0.0
    with _network_lock:
        if _last_network_sample:
            previous_time, previous_sent, previous_received = _last_network_sample
            elapsed = max(now - previous_time, 0.001)
            sent_rate = max(0, counters.bytes_sent - previous_sent) / elapsed
            received_rate = max(0, counters.bytes_recv - previous_received) / elapsed
        _last_network_sample = (now, counters.bytes_sent, counters.bytes_recv)
    return sent_rate, received_rate


def _remember(cpu_percent, memory_percent, sampled_at):
    point = {
        "sampled_at": sampled_at.isoformat(),
        "label": timezone.localtime(sampled_at).strftime("%H:%M:%S"),
        "cpu": round(cpu_percent, 1),
        "memory": round(memory_percent, 1),
    }
    with _history_lock:
        _history.append(point)
        return list(_history)


def collect_system_metrics():
    sampled_at = timezone.now()
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk_root = str(settings.BASE_DIR.drive + "\\") if settings.BASE_DIR.drive else "/"
    disk = psutil.disk_usage(disk_root)
    sent_rate, received_rate = _network_rates()
    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.get_current_timezone())
    history = _remember(cpu_percent, memory.percent, sampled_at)
    system_name = platform.system()
    system_release = platform.release()

    return {
        "sampled_at": sampled_at.isoformat(),
        "server": {
            "name": socket.gethostname(),
            "address": _host_address(),
            "os": f"{system_name} {system_release}",
            "uptime": _format_uptime((sampled_at - boot_time).total_seconds()),
            "status": "online",
        },
        "metrics": [
            {
                "key": "cpu", "label": "CPU 使用率", "value": round(cpu_percent, 1),
                "unit": "%", "percentage": round(cpu_percent, 1), "color": "#409eff",
                "detail": f"{psutil.cpu_count(logical=True) or 0} 个逻辑核心",
            },
            {
                "key": "memory", "label": "内存使用", "value": round(memory.used / 1024 ** 3, 1),
                "unit": f" / {memory.total / 1024 ** 3:.1f} GB", "percentage": round(memory.percent, 1),
                "color": "#43a86b", "detail": f"可用 {_format_bytes(memory.available)}",
            },
            {
                "key": "disk", "label": "磁盘使用", "value": round(disk.percent, 1),
                "unit": "%", "percentage": round(disk.percent, 1), "color": "#d9902f",
                "detail": f"{_format_bytes(disk.used)} / {_format_bytes(disk.total)}",
            },
            {
                "key": "network", "label": "网络吞吐", "value": round((sent_rate + received_rate) / 1024 ** 2, 2),
                "unit": " MB/s", "percentage": None, "color": "#e15b64",
                "detail": f"上传 {_format_bytes(sent_rate)}/s · 下载 {_format_bytes(received_rate)}/s",
            },
        ],
        "chart": {
            "labels": [point["label"] for point in history],
            "timestamps": [point["sampled_at"] for point in history],
            "cpu": [point["cpu"] for point in history],
            "memory": [point["memory"] for point in history],
        },
    }
