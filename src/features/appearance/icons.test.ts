import { readFileSync, readdirSync } from 'node:fs'
import { compileTemplate, parse } from '@vue/compiler-sfc'
import { describe, expect, it } from 'vitest'

const sourceRoot = new URL('../../', import.meta.url)
const read = (file: string) => readFileSync(new URL(file, sourceRoot), 'utf8')

describe('semantic icon colors', () => {
  it('defines the shared functional palette and state exceptions', () => {
    const styles = read('style.css')
    for (const color of ['#3478d4', '#8056d9', '#d97706', '#159968', '#dc3545']) {
      expect(styles).toContain(color)
    }
    for (const selector of ['.menu-item.active > .el-icon', '.brand-mark > .el-icon', '.el-button.is-disabled .el-icon', '.el-input.is-disabled .el-icon', '.icon-button:focus-visible']) {
      expect(styles).toContain(selector)
    }
  })

  it('uses functional colors for toolbar entries and navigation', () => {
    const shell = read('App.vue')
    expect(shell).toContain('class="icon-button icon-purple"')
    expect(shell).toContain('class="icon-button icon-success"')
    expect(shell).toContain('navigationIconTone(item.path)')
    expect(shell).toContain("item.command === 'logout' ? 'icon-danger' : 'icon-primary'")
    expect(read('components/NotificationPopover.vue')).toContain('class="icon-button icon-warning"')
  })

  it('keeps pause and resume colors tied to the current action', () => {
    for (const file of ['views/Accounts.vue', 'views/UserManagement.vue', 'views/RoleManagement.vue']) {
      const source = read(file)
      const record = file.includes('Accounts') ? 'item' : 'row'
      expect(source).toContain(`:class="{ 'icon-danger': ${record}.is_active, 'icon-success': !(${record}.is_active) }"`)
    }
  })

  it('compiles every application template with semantic classes', () => {
    const checkDirectory = (directory: URL) => {
      for (const entry of readdirSync(directory, { withFileTypes: true })) {
        const file = new URL(entry.name + (entry.isDirectory() ? '/' : ''), directory)
        if (entry.isDirectory()) checkDirectory(file)
        else if (entry.name.endsWith('.vue')) {
          const parsed = parse(readFileSync(file, 'utf8'))
          expect(parsed.errors, file.pathname).toEqual([])
          if (!parsed.descriptor.template) continue
          const result = compileTemplate({ source: parsed.descriptor.template.content, filename: file.pathname, id: 'icon-colors' })
          expect(result.errors, file.pathname).toEqual([])
        }
      }
    }
    checkDirectory(sourceRoot)
  })
})
