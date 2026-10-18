<template>
  <router-view v-if="route.path === '/login'" />
  <div v-else class="shell">
    <Transition name="slide-up"><LockScreen v-if="screenLocked" :user="authUser" @unlocked="unlockScreen" @logout="logout" /></Transition>
    <div v-if="systemSettings?.watermark_enabled" class="watermark-layer" aria-hidden="true"><span v-for="item in watermarkItems" :key="item" :style="watermarkStyle">{{ watermarkContent }}</span></div>
    <aside class="sidebar" :class="{ collapsed }">
      <div class="brand"><div class="brand-mark"><el-icon class="icon-primary"><Grid /></el-icon></div><span v-if="!collapsed" class="brand-name">FileHub</span></div>
      <el-scrollbar class="menu-scroll"><div v-for="group in groups" :key="group.title" class="menu-group"><div v-if="!collapsed" class="group-title">{{ group.title }}</div><router-link v-for="item in group.items" :key="item.path" :to="item.path" class="menu-item" :class="{ active: route.path === item.path }" :title="collapsed ? item.label : ''"><el-icon :class="navigationIconTone(item.path)"><component :is="item.icon" /></el-icon><span v-if="!collapsed">{{ item.label }}</span></router-link></div></el-scrollbar>
      <div class="sidebar-bottom"><router-link v-if="canAccess('/settings')" to="/settings" class="menu-item" :class="{ active: route.path === '/settings' }"><el-icon class="icon-primary"><Setting /></el-icon><span v-if="!collapsed">设置</span></router-link><button class="collapse-button" @click="collapsed = !collapsed"><el-icon class="icon-primary"><Expand v-if="collapsed" /><Fold v-else /></el-icon><span v-if="!collapsed">收起菜单</span></button><div v-if="!collapsed" class="sidebar-version"><span>FileHub</span><span>v1.0.0</span></div></div>
    </aside>
    <main class="main-area"><header class="topbar"><div class="breadcrumb"><span>控制台</span><el-icon class="icon-primary"><ArrowRight /></el-icon><strong>{{ pageTitle }}</strong></div><NotificationTicker v-if="canViewNotifications" :item="latestNotification" @open="openFileConfigs" /><div class="top-actions"><el-tooltip content="GitHub 项目"><a v-if="systemSettings?.github_url" class="icon-button icon-purple" :href="systemSettings.github_url" target="_blank" rel="noopener noreferrer" aria-label="打开 GitHub 项目"><svg class="github-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 .7a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.05c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.74.08-.74 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.8 1.3 3.49.99.11-.77.42-1.3.76-1.6-2.67-.3-5.47-1.34-5.47-5.95 0-1.31.47-2.38 1.24-3.22-.12-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23A11.5 11.5 0 0 1 12 7.34c1.02 0 2.05.15 3.01.45 2.29-1.55 3.3-1.23 3.3-1.23.66 1.65.24 2.87.12 3.17.77.84 1.24 1.91 1.24 3.22 0 4.62-2.81 5.65-5.48 5.94.43.37.81 1.1.81 2.22v3.3c0 .32.22.69.83.57A12 12 0 0 0 12 .7Z" /></svg></a></el-tooltip><NotificationPopover v-if="canViewNotifications" :items="notifications" :unread-count="unreadCount" :loading="notificationsLoading" :error="notificationsError" @open="openNotification" @read="readNotification" @read-all="readAllNotifications" @refresh="refreshNotifications()" /><el-tooltip content="锁定屏幕"><button class="icon-button icon-success" type="button" aria-label="锁定屏幕" @click="lockScreen"><el-icon class="icon-success"><Lock /></el-icon></button></el-tooltip><el-dropdown ref="userDropdown" trigger="hover" placement="bottom-end" :show-timeout="100" :hide-timeout="160" popper-class="user-dropdown-popper" @command="handleUserCommand"><button class="user-menu" type="button" aria-label="打开用户菜单" aria-haspopup="menu" @click="openUserMenuOnTouch"><el-avatar :size="30" style="background:#e8f1ff;color:#3478d4">{{ (authUser?.name || authUser?.username || 'U').slice(0, 1).toUpperCase() }}</el-avatar><span>{{ authUser?.name || authUser?.username }}</span><el-icon class="icon-primary"><ArrowDown /></el-icon></button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="item in userMenuItems" :key="item.command" :command="item.command" :icon="userMenuIcons[item.command]" :divided="item.divided" :class="item.command === 'logout' ? 'icon-danger' : 'icon-primary'">{{ item.label }}</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></header><section class="content-area"><router-view /></section><footer class="app-footer"><span>FileHub 运维控制台</span><span>系统运行正常 <i class="online-dot"></i></span></footer></main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { HomeFilled, Files, Document, Setting, Expand, Fold, ArrowDown, ArrowRight, Grid, Key, FolderOpened, List, Collection, UserFilled, Lock, SwitchButton, Monitor } from '@element-plus/icons-vue'
import { api, clearAuth, type ConfigNotification } from './api'
import { authUser, canAccess } from './composables/useAuth'
import { refreshSettings, systemSettings } from './composables/useSettings'
import { buildUserMenu } from './features/profile/model'
import LockScreen from './components/LockScreen.vue'
import NotificationPopover from './components/NotificationPopover.vue'
import NotificationTicker from './components/NotificationTicker.vue'
import { useNotifications } from './composables/useNotifications'
const route = useRoute(); const router = useRouter(); const collapsed = ref(false)
const userDropdown = ref<{ handleOpen: () => void } | null>(null)
const screenLocked = ref(localStorage.getItem('filehub_screen_locked') === '1')
const {
  items: notifications, unreadCount, latest: latestNotification, loading: notificationsLoading,
  error: notificationsError, canView: canViewNotifications, refresh: refreshNotifications,
  markRead: markNotificationRead, markAllRead: markAllNotificationsRead,
} = useNotifications(screenLocked)
let idleLockTimer: ReturnType<typeof setTimeout> | undefined
const navigationIconTones: Record<string, string> = { '/accounts': 'icon-success', '/roles': 'icon-success', '/command-control': 'icon-danger', '/file-configs': 'icon-warning', '/file-lists': 'icon-purple', '/file-audits': 'icon-purple', '/operation-audits': 'icon-purple', '/command-executions': 'icon-success' }
const navigationIconTone = (path: string) => navigationIconTones[path] || 'icon-primary'
const menuGroups = [
  { title: '总览', items: [{ label: '概览', path: '/', icon: HomeFilled }] },
  { title: '资源管理', items: [{ label: '项目管理', path: '/projects', icon: Collection }, { label: '账号管理', path: '/accounts', icon: Key }, { label: '文件管理', path: '/file-configs', icon: FolderOpened }, { label: '文件列表', path: '/file-lists', icon: List }] },
  { title: '运维', items: [{ label: '文件审计', path: '/file-audits', icon: Files }, { label: '操作审计', path: '/operation-audits', icon: Document }, { label: '命令执行', path: '/command-executions', icon: Monitor }] },
  { title: '系统', items: [{ label: '用户管理', path: '/users', icon: UserFilled }, { label: '角色管理', path: '/roles', icon: Lock }, { label: '命令控制', path: '/command-control', icon: Lock }] },
]
const groups = computed(() => menuGroups.map(group => ({ ...group, items: group.items.filter(item => canAccess(item.path)) })).filter(group => group.items.length))
const userMenuItems = computed(() => buildUserMenu(canAccess('/settings')))
const userMenuIcons = { settings: Setting, logout: SwitchButton }
const titles: Record<string, string> = { '/': '概览', '/projects': '项目管理', '/accounts': '账号管理', '/file-configs': '文件管理', '/file-lists': '文件列表', '/file-audits': '文件审计', '/operation-audits': '操作审计', '/command-executions': '命令执行', '/users': '用户管理', '/roles': '角色管理', '/command-control': '命令控制', '/settings': '设置' }
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
