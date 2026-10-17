import axios from 'axios'

export const api = axios.create({ baseURL: '/api', timeout: 5000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('confighub_token')
  if (token) config.headers.Authorization = `Token ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && location.pathname !== '/login') {
      localStorage.removeItem('confighub_token')
      localStorage.removeItem('confighub_user')
      location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export interface User {
  id: number
  username: string
  email: string
  name: string
  is_active: boolean
  is_staff: boolean
  is_superuser: boolean
  date_joined: string
  last_login: string | null
  roles: { id: number; name: string; code: string; is_active: boolean }[]
  permissions: string[]
}

export async function login(username: string, password: string) {
  const response = await api.post<{ token: string; user: User }>('/auth/login/', { username, password })
  localStorage.setItem('confighub_token', response.data.token)
  localStorage.setItem('confighub_user', JSON.stringify(response.data.user))
  return response.data
}

export function clearAuth() {
  localStorage.removeItem('confighub_token')
  localStorage.removeItem('confighub_user')
}

export interface DashboardData {
  sampled_at: string
  server: { name: string; address: string; os: string; uptime: string; status: string }
  metrics: { key: string; label: string; value: number; unit: string; percentage: number | null; color: string; detail: string }[]
  chart: { labels: string[]; timestamps: string[]; cpu: number[]; memory: number[] }
  resources: { key: string; label: string; count: number; description: string; path: string }[]
  activity: { id: number; title: string; detail: string; operator: string; occurred_at: string; type: string }[]
}

export interface SystemSettings {
  font_size: 14 | 16 | 18
  watermark_enabled: boolean
  watermark_mode: 'username' | 'custom'
  watermark_text: string
  watermark_content?: string
  watermark_opacity: number
  watermark_rotation: number
  file_audit_retention_days: number
  operation_audit_retention_days: number
  can_edit_global: boolean
  updated_at: string
}

export interface SettingsResponse {
  settings: SystemSettings
  user: User
}
