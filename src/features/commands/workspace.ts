import { computed, reactive, ref } from 'vue'
import type { CommandExecution } from '../../api'
import { defaultK8sCommand, terminalStatuses } from './model'

export type CommandMode = 'shell' | 'k8s'
export type CommandSection = CommandMode | 'history'

function createDraft(mode: CommandMode) {
  return { mode, file_config_id: null as number | null, working_directory: '/root', remote_file_id: null as number | null, command: '', commandEdited: false, generatedCommand: '', submissionError: '' }
}

export function createCommandWorkspace() {
  const activeSection = ref<CommandSection>('shell')
  const drafts = reactive({ shell: createDraft('shell'), k8s: createDraft('k8s') })
  const form = computed(() => drafts[activeSection.value === 'k8s' ? 'k8s' : 'shell'])
  const historyMode = ref<CommandMode | ''>('')
  const page = ref(1)
  function changeHistoryMode() { page.value = 1 }
  function changeMachine() {
    form.value.remote_file_id = null
    form.value.generatedCommand = ''
    if (form.value.mode === 'k8s' && !form.value.commandEdited) form.value.command = ''
  }
  function changeFile(path: string) {
    const draft = form.value
    if (draft.mode !== 'k8s') return
    const next = defaultK8sCommand(path)
    if (!draft.commandEdited || !draft.command || draft.command === draft.generatedCommand) {
      draft.command = next
      draft.commandEdited = false
    }
    draft.generatedCommand = next
  }
  function payload() {
    const { mode, file_config_id, working_directory, remote_file_id, command } = form.value
    return { mode, file_config_id, working_directory, remote_file_id: mode === 'shell' ? null : remote_file_id, command }
  }
  return { activeSection, drafts, form, historyMode, page, changeHistoryMode, changeMachine, changeFile, payload }
}

export function createExecutionOutput(dependencies: {
  load: (id: number) => Promise<CommandExecution>
  connect: (execution: CommandExecution) => void
  disconnect: () => void
}) {
  const visible = ref(false)
  const loading = ref(false)
  const error = ref('')
  const execution = ref<CommandExecution | null>(null)
  let requestId = 0
  function display(target: CommandExecution) {
    execution.value = target
    if (!terminalStatuses.includes(target.status)) dependencies.connect(execution.value)
  }
  function showCreated(target: CommandExecution) {
    requestId++
    dependencies.disconnect()
    error.value = ''
    loading.value = false
    visible.value = true
    display(target)
  }
  async function open(id: number) {
    const currentRequest = ++requestId
    dependencies.disconnect()
    execution.value = null
    error.value = ''
    loading.value = true
    visible.value = true
    try {
      const target = await dependencies.load(id)
      if (currentRequest === requestId && visible.value) display(target)
    } catch {
      if (currentRequest === requestId && visible.value) error.value = '加载执行详情失败，请关闭后重试。'
    } finally {
      if (currentRequest === requestId) loading.value = false
    }
  }
  function close() {
    requestId++
    visible.value = false
    loading.value = false
    execution.value = null
    dependencies.disconnect()
  }
  return { visible, loading, error, execution, showCreated, open, close }
}
