import { describe, expect, it } from 'vitest'
import { formatNotificationTime, notificationAction, notificationMachine } from './model'
import type { ConfigNotification } from '../../api'

const notification = {
  event_type: 'updated', host_name: 'web-01', ip_address: '192.0.2.10', occurred_at: '2026-10-17T09:21:54Z',
} as ConfigNotification

describe('config notification presentation', () => {
  it('uses the expected action labels and machine format', () => {
    expect(notificationAction[notification.event_type]).toBe('更改')
    expect(notificationMachine(notification)).toBe('web-01（192.0.2.10）')
  })

  it('formats valid timestamps and preserves invalid values', () => {
    expect(formatNotificationTime(notification.occurred_at)).toMatch(/10-17.*\d{2}:21:54/)
    expect(formatNotificationTime('unknown')).toBe('unknown')
  })
})
