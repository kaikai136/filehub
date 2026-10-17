<template>
  <router-view v-if="route.path === '/login'" />
  <div v-else class="shell">
    <Transition name="slide-up"><LockScreen v-if="screenLocked" :user="authUser" @unlocked="unlockScreen" @logout="logout" /></Transition>
    <div v-if="systemSettings?.watermark_enabled" class="watermark-layer" aria-hidden="true"><span v-for="item in watermarkItems" :key="item" :style="watermarkStyle">{{ watermarkContent }}</span></div>
    <aside class="sidebar" :class="{ collapsed }">
      <div class="brand"><div class="brand-mark"><el-icon><Grid /></el-icon></div><span v-if="!collapsed" class="brand-name">FileHub</span></div>
      <el-scrollbar class="menu-scroll"><div v-for="group in groups" :key="group.title" class="menu-group"><div v-if="!collapsed" class="group-title">{{ group.title }}</div><router-link v-for="item in group.items" :key="item.path" :to="item.path" class="menu-item" :class="{ active: route.path === item.path }" :title="collapsed ? item.label : ''"><el-icon><component :is="item.icon" /></el-icon><span v-if="!collapsed">{{ item.label }}</span></router-link></div></el-scrollbar>
      <div class="sidebar-bottom"><router-link v-if="canAccess('/settings')" to="/settings" class="menu-item" :class="{ active: route.path === '/settings' }"><el-icon><Setting /></el-icon><span v-if="!collapsed">设置</span></router-link><button class="collapse-button" @click="collapsed = !collapsed"><el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon><span v-if="!collapsed">收起菜单</span></button><div v-if="!collapsed" class="sidebar-version"><span>FileHub</span><span>v1.0.0</span></div></div>
    </aside>
    <main class="main-area"><header class="topbar"><div class="breadcrumb"><span>控制台</span><el-icon><ArrowRight /></el-icon><strong>{{ pageTitle }}</strong></div><NotificationTicker v-if="canViewNotifications" :item="latestNotification" @open="openFileConfigs" /><div class="top-actions"><el-input v-model="search" class="global-search" placeholder="搜索功能..." :prefix-icon="Search" /><el-tooltip content="帮助"><button class="icon-button"><el-icon><QuestionFilled /></el-icon></button></el-tooltip><NotificationPopover v-if="canViewNotifications" :items="notifications" :unread-count="unreadCount" :loading="notificationsLoading" :error="notificationsError" @open="openNotification" @read="readNotification" @read-all="readAllNotifications" @refresh="refreshNotifications()" /><el-tooltip content="锁定屏幕"><button class="icon-button" type="button" aria-label="锁定屏幕" @click="lockScreen"><el-icon><Lock /></el-icon></button></el-tooltip><el-dropdown ref="userDropdown" trigger="hover" placement="bottom-end" :show-timeout="100" :hide-timeout="160" popper-class="user-dropdown-popper" @command="handleUserCommand"><button class="user-menu" type="button" aria-label="打开用户菜单" aria-haspopup="menu" @click="openUserMenuOnTouch"><el-avatar :size="30" style="background:#e8f1ff;color:#3478d4">{{ (authUser?.name || authUser?.username || 'U').slice(0, 1).toUpperCase() }}</el-avatar><span>{{ authUser?.name || authUser?.username }}</span><el-icon><ArrowDown /></el-icon></button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="item in userMenuItems" :key="item.command" :command="item.command" :icon="userMenuIcons[item.command]" :divided="item.divided">{{ item.label }}</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></header><section class="content-area"><router-view /></section><footer class="app-footer"><span>FileHub 运维控制台</span><span>系统运行正常 <i class="online-dot"></i></span></footer></main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { HomeFilled, Files, Document, Setting, Expand, Fold, ArrowDown, ArrowRight, Search, QuestionFilled, Grid, Key, FolderOpened, List, Collection, UserFilled, Lock, SwitchButton } from '@element-plus/icons-vue'
import { api, clearAuth, type ConfigNotification } from './api'
import { authUser, canAccess } from './composables/useAuth'
import { refreshSettings, systemSettings } from './composables/useSettings'
import { buildUserMenu } from './features/profile/model'
import LockScreen from './components/LockScreen.vue'
import NotificationPopover from './components/NotificationPopover.vue'
import NotificationTicker from './components/NotificationTicker.vue'
import { useNotifications } from './composables/useNotifications'
const route = useRoute(); const router = useRouter(); const collapsed = ref(false); const search = ref('')
const userDropdown = ref<{ handleOpen: () => void } | null>(null)
const screenLocked = ref(localStorage.getItem('filehub_screen_locked') === '1')
const {
  items: notifications, unreadCount, latest: latestNotification, loading: notificationsLoading,
  error: notificationsError, canView: canViewNotifications, refresh: refreshNotifications,
  markRead: markNotificationRead, markAllRead: markAllNotificationsRead,
} = useNotifications(screenLocked)
let idleLockTimer: ReturnType<typeof setTimeout> | undefined
const menuGroups = [
  { title: '总览', items: [{ label: '概览', path: '/', icon: HomeFilled }] },
  { title: '资源管理', items: [{ label: '项目管理', path: '/projects', icon: Collection }, { label: '账号管理', path: '/accounts', icon: Key }, { label: '文件管理', path: '/file-configs', icon: FolderOpened }, { label: '文件列表', path: '/file-lists', icon: List }] },
  { title: '运维', items: [{ label: '文件审计', path: '/file-audits', icon: Files }, { label: '操作审计', path: '/operation-audits', icon: Document }] },
  { title: '系统', items: [{ label: '用户管理', path: '/users', icon: UserFilled }, { label: '角色管理', path: '/roles', icon: Lock }] },
]
const groups = computed(() => menuGroups.map(group => ({ ...group, items: group.items.filter(item => canAccess(item.path)) })).filter(group => group.items.length))
const userMenuItems = computed(() => buildUserMenu(canAccess('/settings')))
const userMenuIcons = { settings: Setting, logout: SwitchButton }
const titles: Record<string, string> = { '/': '概览', '/projects': '项目管理', '/accounts': '账号管理', '/file-configs': '文件管理', '/file-lists': '文件列表', '/file-audits': '文件审计', '/operation-audits': '操作审计', '/users': '用户管理', '/roles': '角色管理', '/settings': '设置' }
const pageTitle = computed(() => titles[route.path] || '资源管理')
const watermarkItems = Array.from({ length: 30 }, (_, index) => index)
const watermarkStyle = computed(() => ({ opacity: (systemSettings.value?.watermark_opacity || 12) / 100, transform: `rotate(${systemSettings.value?.watermark_rotation || -20}deg)` }))
const watermarkContent = computed(() => systemSettings.value?.watermark_content || (systemSettings.value?.watermark_mode === 'username' ? authUser.value?.username : systemSettings.value?.watermark_text) || '')
function resetIdleLock() {
  if (idleLockTimer) clearTimeout(idleLockTimer)
  if (route.path === '/login' || screenLocked.value) return
  idleLockTimer = setTimeout(lockScreen, 60 * 60 * 1000)
}
function lockScreen() {
  if (idleLockTimer) clearTimeout(idleLockTimer)
  localStorage.setItem('filehub_screen_locked', '1')
  screenLocked.value = true
}
function unlockScreen() {
  localStorage.removeItem('filehub_screen_locked')
  screenLocked.value = false
  resetIdleLock()
}
async function logout() { try { await api.post('/auth/logout/') } catch { /* token may already be expired */ } unlockScreen(); authUser.value = null; clearAuth(); ElMessage.success('已退出登录'); router.push('/login') }
function handleUserCommand(command: string | number | object) {
  if (command === 'settings') router.push('/settings')
  else if (command === 'logout') logout()
}
function openUserMenuOnTouch() {
  if (window.matchMedia('(hover: none)').matches) userDropdown.value?.handleOpen()
}
function openFileConfigs() { router.push('/file-configs') }
async function readNotification(item: ConfigNotification) {
  try { await markNotificationRead(item) } catch { ElMessage.error('标记通知已读失败') }
}
async function readAllNotifications() {
  try { await markAllNotificationsRead() } catch { ElMessage.error('全部已读操作失败') }
}
async function openNotification(item: ConfigNotification) {
  try { await markNotificationRead(item) } catch { /* Navigation remains available if read state fails. */ }
  openFileConfigs()
}
onMounted(() => {
  if (localStorage.getItem('confighub_token')) refreshSettings().catch(() => undefined)
  document.addEventListener('mousedown', resetIdleLock)
  resetIdleLock()
})
onUnmounted(() => {
  if (idleLockTimer) clearTimeout(idleLockTimer)
  document.removeEventListener('mousedown', resetIdleLock)
})
watch(() => route.path, resetIdleLock)
</script>
