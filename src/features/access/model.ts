export interface SessionUser {
  id: number
  username: string
  name: string
  is_superuser: boolean
  permissions: string[]
}

export const routePermissions: Record<string, string> = {
  '/': 'dashboard.view', '/projects': 'projects.view', '/accounts': 'accounts.view',
  '/file-configs': 'file_configs.view', '/file-lists': 'file_lists.view',
  '/file-audits': 'file_audit.view', '/operation-audits': 'operation_audit.view', '/settings': 'settings.view',
  '/command-executions': 'command_execution.view',
}

export function can(user: SessionUser | null, permission: string) {
  return Boolean(user && (user.is_superuser || user.permissions?.includes(permission)))
}

export function canVisit(user: SessionUser | null, path: string) {
  if (!user) return false
  if (path === '/forbidden') return true
  if (path === '/users' || path === '/roles') return user.is_superuser
  const permission = routePermissions[path]
  return Boolean(permission && can(user, permission))
}

export function landingPage(user: SessionUser | null) {
  return Object.keys(routePermissions).find(path => canVisit(user, path)) || (user?.is_superuser ? '/users' : '/forbidden')
}

export function changePermission(values: string[], key: string, checked: boolean) {
  const module = key.split('.')[0]
  const view = `${module}.view`
  const result = new Set(values)
  if (checked) { result.add(key); result.add(view) }
  else { result.delete(key); if (key === view) for (const value of result) if (value.startsWith(`${module}.`)) result.delete(value) }
  return [...result]
}
