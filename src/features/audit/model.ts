export type DiffLineKind = 'meta' | 'hunk' | 'added' | 'removed' | 'context'

export interface DiffLine { text: string; kind: DiffLineKind }

export function parseUnifiedDiff(value: string): DiffLine[] {
  return value.split(/(?<=\n)/).filter(Boolean).map(text => {
    const kind: DiffLineKind = text.startsWith('+++') || text.startsWith('---')
      ? 'meta'
      : text.startsWith('@@') ? 'hunk'
        : text.startsWith('+') ? 'added'
          : text.startsWith('-') ? 'removed' : 'context'
    return { text: text.replace(/\n$/, ''), kind }
  })
}

export function auditQuery(filters: Record<string, unknown>, page: number, pageSize: number) {
  const params: Record<string, string | number> = { page, page_size: pageSize }
  for (const [key, value] of Object.entries(filters)) {
    if (Array.isArray(value)) {
      if (value[0]) params.start_time = String(value[0])
      if (value[1]) params.end_time = String(value[1])
    } else if (value !== undefined && value !== null && String(value).trim()) params[key] = String(value).trim()
  }
  return params
}
