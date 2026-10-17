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
})
