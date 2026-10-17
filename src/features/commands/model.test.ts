import { describe, expect, it } from 'vitest'
import { defaultK8sCommand, elapsed, shellQuote, statusType } from './model'
import type { CommandExecution } from '../../api'

describe('command execution model', () => {
  it('quotes remote paths and builds a kubectl apply command', () => {
    expect(defaultK8sCommand('/srv/app deploy/config.yaml')).toBe("kubectl apply -f '/srv/app deploy/config.yaml'")
    expect(shellQuote("/tmp/user's.yaml")).toBe("'/tmp/user'\"'\"'s.yaml'")
    expect(defaultK8sCommand('')).toBe('')
  })

  it('maps statuses and calculates elapsed time', () => {
    expect(statusType('succeeded')).toBe('success')
    expect(statusType('failed')).toBe('danger')
    const execution = { created_at: '2026-01-01T00:00:00Z', started_at: '2026-01-01T00:00:01Z', finished_at: '2026-01-01T00:01:03Z' } as CommandExecution
    expect(elapsed(execution)).toBe('1分2秒')
  })
})
