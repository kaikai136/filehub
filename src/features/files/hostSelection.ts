interface Machine {
  id: number; project_id: number; machine_name: string; host_name: string
  ip_address: string; port: number; account_name: string; file_path: string
}

export function hostsForProject<T extends Machine>(hosts: T[], projectId?: number): T[] {
  return projectId === undefined ? [] : hosts.filter(host => host.project_id === projectId)
}

export function fileManagementConfigs<T extends { file_path: string }>(configs: T[]): T[] {
  return configs.filter(config => config.file_path.trim().length > 0)
}

export function machineLabel(host: Machine) {
  const name = host.machine_name || host.host_name
  return `${name} · ${host.ip_address}`
}
