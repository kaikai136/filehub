import { shallowRef } from 'vue'
import { api, type SystemSettings } from '../api'

export const systemSettings = shallowRef<SystemSettings | null>(null)

export function applySystemSettings(settings: SystemSettings) {
  systemSettings.value = settings
  document.documentElement.style.fontSize = `${settings.font_size}px`
  document.documentElement.style.setProperty('--system-font-size', `${settings.font_size}px`)
  document.documentElement.dataset.uiFontSize = String(settings.font_size)
  const delta = settings.font_size - 16
  document.documentElement.style.setProperty('--el-font-size-base', `${16 + delta}px`)
  document.documentElement.style.setProperty('--el-font-size-small', `${15 + delta}px`)
  document.documentElement.style.setProperty('--el-font-size-extra-small', `${14 + delta}px`)
}

export async function refreshSettings() {
  const { data } = await api.get<Pick<SystemSettings, 'font_size' | 'watermark_enabled' | 'watermark_mode' | 'watermark_text' | 'watermark_content' | 'watermark_opacity' | 'watermark_rotation'>>('/appearance/')
  const settings = { ...(systemSettings.value || { font_size: 16, watermark_enabled: false, watermark_mode: 'username', watermark_text: 'FileHub', watermark_opacity: 12, watermark_rotation: -20, file_audit_retention_days: 180, operation_audit_retention_days: 180, can_edit_global: false, updated_at: '' }), ...data } as SystemSettings
  applySystemSettings(settings)
  return data
}
