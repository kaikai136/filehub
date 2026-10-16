export interface Project { id: number; name: string; parent_id: number | null; sort_order: number; path: string }
export interface ProjectNode extends Project { label: string; children: ProjectNode[]; count: number }
export interface Config {
  id: number; revision: number; project: string; project_id: number; project_path: string
  host_name: string; ip_address: string; machine_name: string; port: number; file_path: string
  account_id: number; account_name: string; updated_at: string; connection_status: string; connection_error: string
  specifications: { cpu?: number; memory_bytes?: number; disk_bytes?: number; system?: string; arch?: string }
  platform_type: string; inspection_status: string; inspection_error: string
}
export const columns = [
  { key: 'project_path', label: '项目分组', width: 150 },
  { key: 'host_name', label: '节点名称', width: 160 },
  { key: 'ip_address', label: 'IP地址', width: 150 }, { key: 'machine_name', label: '机器名称', width: 140 },
  { key: 'specifications', label: '主机规格', width: 240 }, { key: 'platform_type', label: '平台类型', width: 105 },
  { key: 'updated_at', label: '更新时间', width: 180 }, { key: 'connection_status', label: '状态', width: 120 },
  { key: 'actions', label: '操作', width: 132 },
] as const
export function projectTree(projects: Project[], configs: { project_id: number }[] = []): ProjectNode[] {
  const nodes = new Map(projects.map(p => [p.id, { ...p, label: p.name, children: [] as ProjectNode[], count: configs.filter(c => c.project_id === p.id).length }]))
  const roots: ProjectNode[] = []
  for (const node of nodes.values()) {
    const parent = node.parent_id === null ? undefined : nodes.get(node.parent_id)
    if (parent) parent.children.push(node); else roots.push(node)
  }
  function collect(items: ProjectNode[]) {
    items.sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
    for (const item of items) { collect(item.children); item.count += item.children.reduce((sum, child) => sum + child.count, 0) }
  }
  collect(roots)
  return roots
}
export function descendantIds(projects: Project[], selected: number | null): Set<number> {
  if (selected === null) return new Set(projects.map(p => p.id))
  const ids = new Set([selected])
  let changed = true
  while (changed) {
    changed = false
    for (const p of projects) if (p.parent_id !== null && ids.has(p.parent_id) && !ids.has(p.id)) { ids.add(p.id); changed = true }
  }
  return ids
}
export function filterHosts(configs: Config[], projects: Project[], selected: number | null, query: string, status: string) {
  const ids = descendantIds(projects, selected), search = query.trim().toLowerCase()
  return configs.filter(c => ids.has(c.project_id) && (!status || c.connection_status === status) && (!search || `${c.host_name} ${c.machine_name} ${c.ip_address}`.toLowerCase().includes(search)))
}
export function sortHosts(configs: Config[], field: string, descending: boolean) {
  return [...configs].sort((a, b) => {
    const left = String(a[field as keyof Config] ?? ''), right = String(b[field as keyof Config] ?? '')
    return (descending ? -1 : 1) * left.localeCompare(right, 'zh-CN', { numeric: true })
  })
}
export function pageHosts<T>(rows: T[], page: number, size: number) { return rows.slice((page - 1) * size, page * size) }
export function retainSelection(ids: number[], rows: { id: number }[]) { const allowed = new Set(rows.map(row => row.id)); return ids.filter(id => allowed.has(id)) }
export async function runLimited<T>(items: T[], action: (item: T) => Promise<void>, concurrency = 3) {
  let next = 0
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, async () => {
    while (next < items.length) { const index = next++; await action(items[index]!) }
  }))
}
export function errorText(error: any) {
  const data = error?.response?.data
  return (typeof data?.detail === 'string' ? data.detail : Array.isArray(data) ? data.join('；') : '') || error?.message || '操作失败'
}
export function formatBytes(value?: number) { return value ? `${(value / 1024 ** 3).toFixed(1)}G` : '—' }
export function connectionText(value: string) { return value === 'success' ? '已验证' : value === 'error' ? '验证失败' : '未验证' }
export interface ImportRow { row: number; host_name: string; project_path: string; status: 'ready' | 'duplicate' | 'error'; error: string }
export function canImport(rows: ImportRow[], token: string | null) { return Boolean(token && rows.length && rows.every(row => row.status !== 'error')) }
