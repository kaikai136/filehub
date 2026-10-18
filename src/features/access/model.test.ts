import { describe, expect, it } from 'vitest'
import { canVisit, changePermission, landingPage, type SessionUser } from './model'

const user = (permissions: string[] = [], is_superuser = false): SessionUser => ({
  id: 1, username: 'tester', name: '测试用户', is_superuser, permissions,
})

describe('RBAC access model', () => {
  it('filters routes by effective permission, including delegated system pages', () => {
    const viewer = user(['projects.view'])
    expect(canVisit(viewer, '/projects')).toBe(true)
    expect(canVisit(viewer, '/accounts')).toBe(false)
    expect(canVisit(viewer, '/profile')).toBe(false)
    expect(canVisit(viewer, '/users')).toBe(false)
    expect(canVisit(user([], true), '/roles')).toBe(true)
    expect(canVisit(user(['users.view']), '/users')).toBe(true)
    expect(canVisit(user(['roles.view']), '/roles')).toBe(true)
    expect(canVisit(user(['file_audit.view']), '/file-audits')).toBe(true)
    expect(canVisit(user(['file_audit.view']), '/operation-audits')).toBe(false)
    expect(canVisit(user(['command_execution.view']), '/command-executions')).toBe(true)
  })

  it('selecting a write action includes view and removing view clears the module', () => {
    expect(new Set(changePermission([], 'projects.edit', true))).toEqual(new Set(['projects.view', 'projects.edit']))
    expect(changePermission(['projects.view', 'projects.edit', 'projects.delete'], 'projects.view', false)).toEqual([])
  })

  it('uses the first available page and falls back to forbidden', () => {
    expect(landingPage(user(['accounts.view']))).toBe('/accounts')
    expect(landingPage(user(['users.view']))).toBe('/users')
    expect(landingPage(user())).toBe('/forbidden')
  })
})
