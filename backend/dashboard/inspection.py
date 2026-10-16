import base64
import json


def run_command(client, command):
    stdin, stdout, stderr = client.exec_command(command, timeout=15)
    try:
        stdin.close()
        output = stdout.read(65536).decode('utf-8', errors='replace').strip()
        error = stderr.read(8192).decode('utf-8', errors='replace').strip()
        if stdout.channel.recv_exit_status() != 0:
            raise ValueError(error or '无法采集系统信息')
        return output
    finally:
        stdout.close()
        stderr.close()


def inspect_machine(client):
    try:
        platform = run_command(client, 'uname -s').lower()
    except Exception:
        platform = ''
    if platform == 'linux':
        output = run_command(client, '''hostname
getconf _NPROCESSORS_ONLN
awk '/MemTotal/ {print $2}' /proc/meminfo
lsblk -bdno NAME,SIZE,TYPE | awk '$3 == "disk" {sum += $2} END {printf "%.0f\\n", sum}'
(. /etc/os-release; printf '%s\\n' "$PRETTY_NAME")
uname -m''')
        parts = output.splitlines()
        if len(parts) != 6:
            raise ValueError('系统信息返回不完整')
        return {'machine_name': parts[0], 'platform_type': 'linux', 'cpu': int(parts[1]),
                'memory_bytes': int(parts[2]) * 1024, 'disk_bytes': int(parts[3]),
                'system': parts[4], 'arch': parts[5]}
    script = '''$ErrorActionPreference='Stop'; $os=Get-CimInstance Win32_OperatingSystem; $cs=Get-CimInstance Win32_ComputerSystem; $disk=(Get-CimInstance Win32_DiskDrive | Measure-Object -Property Size -Sum).Sum; @{machine_name=$env:COMPUTERNAME; platform_type='windows'; cpu=[int]$cs.NumberOfLogicalProcessors; memory_bytes=[long]$cs.TotalPhysicalMemory; disk_bytes=[long]$disk; system=$os.Caption; arch=$os.OSArchitecture} | ConvertTo-Json -Compress'''
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result = json.loads(run_command(client, 'powershell.exe -NoProfile -NonInteractive -EncodedCommand ' + encoded).lstrip('\ufeff'))
    if result.get('platform_type') != 'windows' or not result.get('machine_name'):
        raise ValueError('未识别的系统信息')
    return result
