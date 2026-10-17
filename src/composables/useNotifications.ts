import { computed, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'
import { api, type ConfigNotification, type NotificationResponse } from '../api'
import { authUser, hasPermission } from './useAuth'

export function useNotifications(screenLocked: Ref<boolean>) {
  const items = ref<ConfigNotification[]>([])
  const unreadCount = ref(0)
  const latest = ref<ConfigNotification | null>(null)
  const loading = ref(false)
  const error = ref('')
  const accessDenied = ref(false)
  const canView = computed(() => hasPermission('file_configs.view') && !accessDenied.value)
  let timer: ReturnType<typeof setInterval> | undefined
  let requestPending = false

  function clearState() {
    items.value = []
    latest.value = null
    unreadCount.value = 0
    error.value = ''
  }

  async function refresh(silent = false) {
    if (!canView.value || screenLocked.value || document.hidden || requestPending) return
    requestPending = true
    if (!silent && !items.value.length) loading.value = true
    try {
      const { data } = await api.get<NotificationResponse>('/notifications/', { params: { limit: 20 } })
      items.value = data.items
      latest.value = data.latest
      unreadCount.value = data.unread_count
      accessDenied.value = false
      error.value = ''
    } catch (requestError: any) {
      if (requestError.response?.status === 403) { accessDenied.value = true; clearState() }
      else error.value = requestError.response?.data?.detail || '通知加载失败'
    } finally {
      loading.value = false
      requestPending = false
    }
  }

  async function markRead(item: ConfigNotification) {
    if (item.is_read) return
    await api.post(`/notifications/${item.id}/read/`)
    item.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  }

  async function markAllRead() {
    if (!unreadCount.value) return
    await api.post('/notifications/read-all/')
    items.value = items.value.map(item => ({ ...item, is_read: true }))
    if (latest.value) latest.value = { ...latest.value, is_read: true }
    unreadCount.value = 0
  }

  function handleVisibility() {
    if (!document.hidden) void refresh(true)
  }

  onMounted(() => {
    void refresh()
    timer = setInterval(() => void refresh(true), 5000)
    document.addEventListener('visibilitychange', handleVisibility)
  })
  onUnmounted(() => {
    if (timer) clearInterval(timer)
    document.removeEventListener('visibilitychange', handleVisibility)
  })
  watch(screenLocked, locked => { if (!locked) void refresh(true) })
  watch(authUser, user => {
    accessDenied.value = false
    if (user && hasPermission('file_configs.view')) void refresh()
    else clearState()
  })

  return { items, unreadCount, latest, loading, error, canView, refresh, markRead, markAllRead }
}
