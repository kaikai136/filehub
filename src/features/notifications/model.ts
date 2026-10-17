import type { ConfigNotification } from '../../api'

export const notificationAction: Record<ConfigNotification['event_type'], string> = {
  created: '新增',
  updated: '更改',
  deleted: '删除',
}

export function notificationMachine(item: ConfigNotification) {
  return item.host_name ? `${item.host_name}（${item.ip_address}）` : item.ip_address
}

export function formatNotificationTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(date).replace(/\//g, '-')
}
