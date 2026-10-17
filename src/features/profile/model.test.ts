import { describe, expect, it } from 'vitest'
import { buildUserMenu, createProfileForm, profilePayload, validateProfile } from './model'

describe('profile model', () => {
  it('hydrates a profile form and strips password fields from user data', () => {
    const form = createProfileForm({ username: 'tester', name: '测试用户', email: 'a@example.com' } as any)
    expect(form).toEqual({ username: 'tester', name: '测试用户', email: 'a@example.com', current_password: '', new_password: '', confirm_password: '' })
  })

  it('validates password confirmation and builds an update payload', () => {
    const form = { username: 'tester', name: ' 测试用户 ', email: ' a@example.com ', current_password: 'old', new_password: 'new123', confirm_password: 'wrong' }
    expect(validateProfile(form)).toBe('两次输入的新密码不一致')
    form.confirm_password = 'new123'
    expect(validateProfile(form)).toBe('')
    expect(profilePayload(form)).toEqual({ name: '测试用户', email: 'a@example.com', current_password: 'old', new_password: 'new123' })
  })

  it('shows settings only when permitted and keeps logout explicit', () => {
    expect(buildUserMenu(false)).toEqual([{ command: 'logout', label: '退出登录', divided: false }])
    expect(buildUserMenu(true).map(item => item.command)).toEqual(['settings', 'logout'])
    expect(buildUserMenu(true).slice(-1)[0]).toMatchObject({ command: 'logout', divided: true })
  })
})
