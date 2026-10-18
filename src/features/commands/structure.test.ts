import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const root = new URL('../../', import.meta.url)
const read = (path: string) => readFileSync(new URL(path, root), 'utf8')

describe('command execution integration', () => {
  it('registers the operations menu, route, and permission', () => {
    expect(read('App.vue')).toContain("path: '/command-executions'")
    expect(read('main.ts')).toContain("path: '/command-executions', component: CommandExecution")
    expect(read('features/access/model.ts')).toContain("'/command-executions': 'command_execution.view'")
  })

  it('provides shell, k8s, machine, file, command, terminal, and stop controls', () => {
    const page = read('views/CommandExecution.vue')
    for (const text of ['Shell', 'K8s', '执行机器', '执行路径', '文件', '命令内容', 'terminal-output', '停止']) expect(page).toContain(text)
  })

  it('only shows file selection for k8s and keeps submission errors with the draft', () => {
    const page = read('views/CommandExecution.vue')
    expect(page).toContain(`<el-form-item v-if="form.mode === 'k8s'" label="文件">`)
    expect(page).toContain('已启用危险命令黑名单')
    expect(page).toContain('v-if="form.submissionError"')
    expect(page).toContain('submittedDraft.submissionError = error.response?.data?.detail')
    expect(page).not.toContain("form.value.command = ''")
  })

  it('uses settings navigation, a separate history section, and a teleported output dialog', () => {
    const page = read('views/CommandExecution.vue')
    for (const text of ['settings-layout', 'settings-nav', "key: 'shell'", "key: 'k8s'", "key: 'history'", 'v-model="historyMode"', '@change="filterHistory"', '<el-dialog', 'append-to-body', '@close="closeOutput"', '@closed="restoreOutputFocus"', 'output.showCreated(data)', 'workspace.payload()']) expect(page).toContain(text)
    expect(page).not.toContain('el-segmented')
    expect(page).toContain('grid-template-columns: repeat(2, minmax(0, 1fr))')
    expect(page.indexOf('output.showCreated(data)')).toBeLessThan(page.indexOf("ElMessage.success('命令已提交')"))
  })
})
