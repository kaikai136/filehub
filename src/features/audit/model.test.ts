import { describe, expect, it } from 'vitest'
import { auditQuery, parseUnifiedDiff } from './model'

describe('audit models', () => {
  it('classifies unified diff lines for highlighting', () => {
    const lines = parseUnifiedDiff('--- old\n+++ new\n@@ -1 +1 @@\n-old\n+new\n context\n')
    expect(lines.map(line => line.kind)).toEqual(['meta', 'meta', 'hunk', 'removed', 'added', 'context'])
  })

  it('builds compact pagination and filter parameters', () => {
    expect(auditQuery({ time: ['2026-01-01T00:00:00', '2026-01-02T00:00:00'], project: ' demo ', ip: '' }, 2, 50)).toEqual({
      page: 2, page_size: 50, start_time: '2026-01-01T00:00:00', end_time: '2026-01-02T00:00:00', project: 'demo',
    })
  })
})
