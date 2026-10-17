import { onUnmounted, ref } from 'vue'
import type { CommandExecution, CommandOutput, CommandStatus } from '../api'
import { terminalStatuses } from '../features/commands/model'

type StreamMessage =
  | { type: 'snapshot'; execution: Partial<CommandExecution> & { outputs: CommandOutput[] } }
  | ({ type: 'output' } & CommandOutput)
  | { type: 'status'; status: CommandStatus; exit_code?: number | null; error_message?: string; started_at?: string; finished_at?: string; output_truncated?: boolean }

export function useCommandStream(onStatus?: () => void) {
  const connected = ref(false)
  let socket: WebSocket | null = null
  let execution: CommandExecution | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined
  let stopped = false

  function mergeOutputs(values: CommandOutput[]) {
    if (!execution) return
    const outputs = new Map((execution.outputs || []).map(item => [item.sequence, item]))
    for (const item of values) outputs.set(item.sequence, item)
    execution.outputs = [...outputs.values()].sort((a, b) => a.sequence - b.sequence)
  }

  function apply(message: StreamMessage) {
    if (!execution) return
    if (message.type === 'snapshot') {
      Object.assign(execution, message.execution)
      mergeOutputs(message.execution.outputs || [])
      if (terminalStatuses.includes(execution.status)) setTimeout(disconnect)
    } else if (message.type === 'output') {
      mergeOutputs([message])
    } else {
      Object.assign(execution, message)
      onStatus?.()
      if (terminalStatuses.includes(message.status)) setTimeout(disconnect)
    }
  }

  function connect(target: CommandExecution) {
    disconnect()
    stopped = false
    execution = target
    if (terminalStatuses.includes(target.status)) return
    const token = localStorage.getItem('confighub_token') || ''
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${location.host}/ws/command-executions/${target.id}/?token=${encodeURIComponent(token)}`)
    socket.onopen = () => { connected.value = true }
    socket.onmessage = event => apply(JSON.parse(event.data) as StreamMessage)
    socket.onclose = () => {
      connected.value = false
      socket = null
      if (!stopped && execution && !terminalStatuses.includes(execution.status)) reconnectTimer = setTimeout(() => connect(execution!), 1500)
    }
  }

  function disconnect() {
    stopped = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = undefined
    if (socket) { socket.onclose = null; socket.close() }
    socket = null
    connected.value = false
  }

  onUnmounted(disconnect)
  return { connected, connect, disconnect }
}
