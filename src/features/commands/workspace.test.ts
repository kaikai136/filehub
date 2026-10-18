import { describe, expect, it, vi } from 'vitest'
import type { CommandExecution } from '../../api'
import { createCommandWorkspace, createExecutionOutput } from './workspace'

const execution = (id: number, status: CommandExecution['status'] = 'running') => ({ id, status, outputs: [] }) as unknown as CommandExecution

describe('command workspace', () => {
  it('defaults to shell and preserves independent drafts across all sections', () => {
    const workspace = createCommandWorkspace()
    expect(workspace.activeSection.value).toBe('shell')
    Object.assign(workspace.form.value, { file_config_id: 1, remote_file_id: 2, working_directory: '/shell', command: 'pwd', commandEdited: true })
    workspace.activeSection.value = 'k8s'
    expect(workspace.form.value.command).toBe('')
    Object.assign(workspace.form.value, { file_config_id: 3, remote_file_id: 4, working_directory: '/k8s' })
    workspace.changeFile('/k8s/app.yaml')
    workspace.activeSection.value = 'history'
    workspace.activeSection.value = 'shell'
    expect(workspace.payload()).toEqual({ mode: 'shell', file_config_id: 1, remote_file_id: null, working_directory: '/shell', command: 'pwd' })
    workspace.activeSection.value = 'k8s'
    expect(workspace.payload()).toEqual({ mode: 'k8s', file_config_id: 3, remote_file_id: 4, working_directory: '/k8s', command: "kubectl apply -f '/k8s/app.yaml'" })
    expect(workspace.form.value.generatedCommand).toBe(workspace.form.value.command)
  })

  it('retains rejected shell drafts and their error independently of k8s', () => {
    const workspace = createCommandWorkspace()
    workspace.form.value.command = 'rm /tmp/file'
    workspace.form.value.remote_file_id = 42
    workspace.form.value.submissionError = 'Shell 安全拦截：禁止执行 rm'
    workspace.activeSection.value = 'k8s'
    expect(workspace.form.value.submissionError).toBe('')
    workspace.form.value.remote_file_id = 7
    expect(workspace.payload().remote_file_id).toBe(7)
    workspace.activeSection.value = 'shell'
    expect(workspace.form.value.command).toBe('rm /tmp/file')
    expect(workspace.form.value.submissionError).toContain('禁止执行 rm')
    expect(workspace.payload().remote_file_id).toBeNull()
    expect(workspace.payload()).not.toHaveProperty('submissionError')
  })

  it('protects manually edited k8s commands through repeated file changes', () => {
    const workspace = createCommandWorkspace()
    workspace.activeSection.value = 'k8s'
    workspace.changeFile('/first.yaml')
    workspace.changeFile('/second.yaml')
    expect(workspace.form.value.command).toContain('/second.yaml')
    workspace.form.value.command = 'kubectl get pods'
    workspace.form.value.commandEdited = true
    workspace.changeFile('/third.yaml')
    workspace.changeFile('/fourth.yaml')
    expect(workspace.form.value.command).toBe('kubectl get pods')
    workspace.changeMachine()
    expect(workspace.form.value.remote_file_id).toBeNull()
    expect(workspace.form.value.command).toBe('kubectl get pods')
    workspace.page.value = 4
    workspace.historyMode.value = 'k8s'
    workspace.changeHistoryMode()
    expect(workspace.page.value).toBe(1)
  })
})

describe('execution output dialog', () => {
  function setup() {
    const connect = vi.fn(), disconnect = vi.fn()
    const load = vi.fn<(id: number) => Promise<CommandExecution>>()
    return { connect, disconnect, load, output: createExecutionOutput({ load, connect, disconnect }) }
  }

  it('opens created tasks immediately and closing only disconnects the subscription', async () => {
    const { output, connect, disconnect, load } = setup()
    output.showCreated(execution(1))
    expect(output.visible.value).toBe(true)
    expect(connect).toHaveBeenCalledWith(output.execution.value)
    output.close()
    expect(disconnect).toHaveBeenCalled()
    expect(output.visible.value).toBe(false)
    load.mockResolvedValue(execution(1))
    await output.open(1)
    expect(load).toHaveBeenCalledWith(1)
    expect(connect).toHaveBeenCalledTimes(2)
  })

  it('shows completed history without opening a stream and clears stale output on failure', async () => {
    const { output, load, connect } = setup()
    load.mockResolvedValueOnce(execution(1, 'succeeded'))
    await output.open(1)
    expect(connect).not.toHaveBeenCalled()
    load.mockRejectedValueOnce(new Error('offline'))
    const pending = output.open(2)
    expect(output.loading.value).toBe(true)
    expect(output.execution.value).toBeNull()
    await pending
    expect(output.error.value).toContain('加载执行详情失败')
    expect(output.loading.value).toBe(false)
  })

  it('ignores old responses after a newer selection or close', async () => {
    const { output, load } = setup()
    let resolveFirst!: (value: CommandExecution) => void
    load.mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve }))
    const first = output.open(1)
    load.mockResolvedValueOnce(execution(2))
    await output.open(2)
    resolveFirst(execution(1))
    await first
    expect(output.execution.value?.id).toBe(2)
    let resolveThird!: (value: CommandExecution) => void
    load.mockImplementationOnce(() => new Promise(resolve => { resolveThird = resolve }))
    const third = output.open(3)
    output.close()
    resolveThird(execution(3))
    await third
    expect(output.visible.value).toBe(false)
    expect(output.execution.value).toBeNull()
  })
})
