const matchLabels = { exact: '精确名称', prefix: '名称前缀', python_version: 'Python 数字版本' }

export function commandMatchLabel(match: unknown): string {
  if (match === 'exact' || match === 'prefix' || match === 'python_version') return matchLabels[match]
  return '未知匹配方式'
}
