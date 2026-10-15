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
  server: { name: string; address: string; os: string; uptime: string; status: string }
  metrics: { key: string; label: string; value: number; unit: string; color: string; trend: string }[]
  chart: { labels: string[]; cpu: number[]; memory: number[] }
  services: { name: string; description: string; status: string; version: string; icon: string; color: string }[]
  activity: { title: string; detail: string; time: string; type: string }[]
}
