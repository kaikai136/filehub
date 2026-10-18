import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { canVisit } from '../access/model'

const read = (file: string) => readFileSync(new URL('../../' + file, import.meta.url), 'utf8')

describe('command control integration', () => {
  it('places command control after roles and registers its permission and route', () => {
    const shell = read('App.vue')
    expect(shell.indexOf("label: '命令控制'")).toBeGreaterThan(shell.indexOf("label: '角色管理'"))
    expect(read('main.ts')).toContain("path: '/command-control', component: CommandControl")
    const user = { id: 1, username: 'viewer', name: 'viewer', is_superuser: false, permissions: [] as string[] }
    expect(canVisit(user, '/command-control')).toBe(false)
    user.permissions.push('command_control.view')
    expect(canVisit(user, '/command-control')).toBe(true)
  })

  it('exposes editable rules, readonly permissions, defaults and versioned saves', () => {
    const page = read('views/CommandControl.vue')
    for (const text of ['v-model="row.command"', 'v-model="row.category"', 'v-model="row.match"', 'v-model="row.enabled"', 'v-if="canEdit"', '/command-control/', 'revision: revision.value', '恢复内置规则', 'K8s 不受此黑名单约束', '语法限制始终生效']) expect(page).toContain(text)
  })
})
