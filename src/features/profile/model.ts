import type { User } from '../../api'

export interface ProfileFormValue {
  username: string
  name: string
  email: string
  current_password: string
  new_password: string
  confirm_password: string
}

export interface UserMenuItem {
  command: 'settings' | 'logout'
  label: string
  divided?: boolean
}

export function buildUserMenu(canOpenSettings: boolean): UserMenuItem[] {
  return [
    ...(canOpenSettings ? [{ command: 'settings' as const, label: '设置' }] : []),
    { command: 'logout', label: '退出登录', divided: canOpenSettings },
  ]
}

export function createProfileForm(user?: User | null): ProfileFormValue {
  return {
    username: user?.username || '',
    name: user?.name || '',
    email: user?.email || '',
    current_password: '',
    new_password: '',
    confirm_password: '',
  }
}

export function validateProfile(form: ProfileFormValue) {
  if (!form.name.trim()) return '姓名不能为空'
  if (form.name.trim().length > 150) return '姓名不能超过 150 个字符'
  if (form.email.length > 254) return '邮箱不能超过 254 个字符'
  if (form.new_password && form.new_password.length < 6) return '新密码至少 6 位'
  if (form.new_password && !form.current_password) return '请输入当前密码'
  if (form.new_password !== form.confirm_password) return '两次输入的新密码不一致'
  return ''
}

export function profilePayload(form: ProfileFormValue) {
  return {
    name: form.name.trim(),
    email: form.email.trim(),
    current_password: form.current_password,
    new_password: form.new_password,
  }
}
