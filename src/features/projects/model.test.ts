import { describe, expect, it } from 'vitest'
import {
  canImport, columns, descendantIds, filterHosts, pageHosts, projectTree,
  retainSelection, runLimited, sortHosts, type Config, type Project,
} from './model'

const projects: Project[] = [
  { id: 1, name: 'root', parent_id: null, sort_order: 0, path: 'root' },
  { id: 2, name: 'child', parent_id: 1, sort_order: 0, path: 'root/child' },
  { id: 3, name: 'other', parent_id: null, sort_order: 1, path: 'other' },
]
const host = (id: number, project_id: number, host_name: string, ip_address: string, connection_status = 'pending'): Config => ({
  id, revision: 0, project_id, project: 'root', project_path: 'root', host_name,
  ip_address, machine_name: 'machine', port: 22, file_path: '/srv', account_id: 1,
  account_name: 'SSH', updated_at: '2026-10-16T00:00:00Z', connection_status,
  connection_error: '', specifications: {}, platform_type: '', inspection_status: 'pending', inspection_error: '',
})
const hosts = [host(1, 1, 'node2', '192.0.2.2'), host(2, 2, 'node1', '192.0.2.1', 'success'), host(3, 3, 'other', '192.0.2.3')]

describe('project host list', () => {
  it('counts descendants and filters by selected project and status', () => {
    expect(projectTree(projects, hosts)[0]?.count).toBe(2)
    expect([...descendantIds(projects, 1)]).toEqual([1, 2])
    expect(filterHosts(hosts, projects, 1, '192.0.2', '').map(row => row.id)).toEqual([1, 2])
    expect(filterHosts(hosts, projects, 1, 'node', 'success').map(row => row.id)).toEqual([2])
    expect(filterHosts(hosts, projects, 1, 'MACHINE', '').map(row => row.id)).toEqual([1, 2])
  })

  it('shows the node name after the project and supports sorting, paging and selection pruning', () => {
    expect(columns.map(column => column.label)).toEqual([
      '项目分组', '节点名称', 'IP地址', '机器名称', '主机规格', '平台类型', '更新时间', '状态', '操作',
    ])
    expect(columns[1].key).toBe('host_name')
    expect(pageHosts(sortHosts(hosts, 'host_name', false), 1, 1)[0]?.host_name).toBe('node1')
    expect(pageHosts(sortHosts(hosts, 'ip_address', false), 2, 1)[0]?.host_name).toBe('node2')
    expect(retainSelection([1, 3], filterHosts(hosts, projects, 1, '', ''))).toEqual([1])
  })

  it('never runs more than three inspections at once', async () => {
    let active = 0, highest = 0
    await runLimited([1, 2, 3, 4, 5, 6], async () => {
      highest = Math.max(highest, ++active)
      await new Promise(resolve => setTimeout(resolve, 1))
      active--
    })
    expect(highest).toBe(3)
  })

  it('requires a valid preview before import confirmation', () => {
    const row = { row: 2, host_name: 'node', project_path: 'root', status: 'ready' as const, error: '' }
    expect(canImport([row], 'signed')).toBe(true)
    expect(canImport([{ ...row, status: 'error' }], 'signed')).toBe(false)
    expect(canImport([row], null)).toBe(false)
  })
})
