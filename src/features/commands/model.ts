import type { CommandExecution, CommandStatus } from '../../api'

export const terminalStatuses: CommandStatus[] = ['succeeded', 'failed', 'stopped', 'timeout']

export const statusLabels: Record<CommandStatus, string> = {
  queued: '排队中', running: '执行中', succeeded: '成功', failed: '失败', stopped: '已停止', timeout: '超时',
}

export function statusType(status: CommandStatus) {
  if (status === 'succeeded') return 'success'
  if (status === 'queued' || status === 'running') return 'primary'
  if (status === 'stopped') return 'info'
  return 'danger'
}

export function defaultK8sCommand(filePath: string) {
  if (!filePath) return ''
  return `kubectl apply -f ${shellQuote(filePath)}`
}

export function shellQuote(value: string) {
  return `'${value.replace(/'/g, `'"'"'`)}'`
}

export function elapsed(execution: CommandExecution, now = Date.now()) {
  const start = execution.started_at ? new Date(execution.started_at).getTime() : new Date(execution.created_at).getTime()
  const end = execution.finished_at ? new Date(execution.finished_at).getTime() : now
  const seconds = Math.max(0, Math.floor((end - start) / 1000))
  const minutes = Math.floor(seconds / 60)
  return minutes ? `${minutes}分${seconds % 60}秒` : `${seconds}秒`
}
