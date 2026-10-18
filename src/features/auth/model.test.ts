import { describe, expect, it } from 'vitest'
import { durationFromMinutes, durationToMinutes, normalizeAppearance, rememberedUsername, rememberUsername } from './model'

describe('login preferences', () => {
  it('round trips duration without rounding', () => {
    for (const minutes of [1, 61, 480, 1440, 43200]) {
      const duration = durationFromMinutes(minutes)
      expect(durationToMinutes(duration.value, duration.unit)).toBe(minutes)
    }
    expect(durationFromMinutes(480)).toEqual({ value: 8, unit: 'hours' })
  })
  it('rejects out of range and fractional minutes', () => {
    for (const value of [undefined, 0, -1, 43201, 1.5, NaN]) expect(durationToMinutes(value, 'minutes')).toBeNull()
    expect(durationToMinutes(31, 'days')).toBeNull()
  })
  it('only remembers a username and removes it when disabled', () => {
    const values = new Map<string, string>()
    const storage = { getItem: (key: string) => values.get(key) || null, setItem: (key: string, value: string) => { values.set(key, value) }, removeItem: (key: string) => { values.delete(key) } }
    rememberUsername(storage, ' admin ', true)
    expect(rememberedUsername(storage)).toBe('admin')
    expect(values.size).toBe(1)
    rememberUsername(storage, 'admin', false)
    expect(rememberedUsername(storage)).toBe('')
  })
  it('normalizes untrusted appearance preferences', () => {
    expect(normalizeAppearance(null)).toEqual({ layout: 'characters', dark: false })
    expect(normalizeAppearance({ layout: 'glass', dark: true })).toEqual({ layout: 'glass', dark: true })
    expect(normalizeAppearance({ layout: 'invalid', dark: 'true' })).toEqual({ layout: 'characters', dark: false })
  })
})
