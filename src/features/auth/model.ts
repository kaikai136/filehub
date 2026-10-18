export type ExpiryUnit = 'minutes' | 'hours' | 'days'
export const expiryFactors: Record<ExpiryUnit, number> = { minutes: 1, hours: 60, days: 1440 }

export function durationFromMinutes(minutes: number) {
  const unit: ExpiryUnit = minutes % 1440 === 0 ? 'days' : minutes % 60 === 0 ? 'hours' : 'minutes'
  return { value: minutes / expiryFactors[unit], unit }
}

export function durationToMinutes(value: number | undefined, unit: ExpiryUnit) {
  const minutes = Number(value) * expiryFactors[unit]
  return Number.isInteger(minutes) && minutes >= 1 && minutes <= 43200 ? minutes : null
}

export function rememberedUsername(storage: Pick<Storage, 'getItem'>) {
  return storage.getItem('filehub_remembered_username') || ''
}

export function rememberUsername(storage: Pick<Storage, 'setItem' | 'removeItem'>, username: string, remember: boolean) {
  if (remember) storage.setItem('filehub_remembered_username', username.trim())
  else storage.removeItem('filehub_remembered_username')
}

export function normalizeAppearance(value: unknown): { layout: 'characters' | 'glass'; dark: boolean } {
  const raw = value && typeof value === 'object' ? value as Record<string, unknown> : {}
  return { layout: raw.layout === 'glass' ? 'glass' : 'characters', dark: raw.dark === true }
}
