import { describe, expect, it } from 'vitest'
import { fileManagementConfigs, hostsForProject, machineLabel } from './hostSelection'

const hosts = [
  { id: 1, project_id: 10, machine_name: 'server-a', host_name: 'node', ip_address: '192.0.2.1', port: 22, account_name: 'SSH', file_path: '' },
  { id: 2, project_id: 20, machine_name: '', host_name: 'node', ip_address: '192.0.2.2', port: 2222, account_name: 'SSH', file_path: '' },
  { id: 3, project_id: 10, machine_name: 'server-a', host_name: 'node', ip_address: '192.0.2.1', port: 22, account_name: 'Read only', file_path: '/srv' },
]

describe('file management machine selection', () => {
  it('shows only configured file paths while keeping project machines available for selection', () => {
    const records = [...hosts, { ...hosts[0]!, id: 4, file_path: '   ' }]
    expect(fileManagementConfigs(records).map(host => host.id)).toEqual([3])
    expect(hostsForProject(records, 10).map(host => host.id)).toEqual([1, 3, 4])
    expect(fileManagementConfigs([hosts[0]!, hosts[1]!])).toEqual([])
    expect(fileManagementConfigs([{ ...hosts[0]!, file_path: '/' }])).toHaveLength(1)
  })

  it('requires a project and limits machines to its exact ID, including an empty project', () => {
    expect(hostsForProject(hosts)).toEqual([])
    expect(hostsForProject(hosts, 10).map(host => host.id)).toEqual([1, 3])
    expect(hostsForProject(hosts, 20).map(host => host.id)).toEqual([2])
    expect(hostsForProject(hosts, 30)).toEqual([])
    expect(hostsForProject(hosts, 20).find(host => host.id === 1)).toBeUndefined()
  })

  it('shows only the node name and IP address', () => {
    expect(machineLabel(hosts[0]!)).toBe('server-a · 192.0.2.1')
    expect(machineLabel(hosts[1]!)).toBe('node · 192.0.2.2')
    expect(machineLabel(hosts[2]!)).toBe('server-a · 192.0.2.1')
    expect(machineLabel(hosts[0]!)).not.toContain(':22')
  })
})
