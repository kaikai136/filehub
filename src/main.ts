import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import ModulePage from './views/ModulePage.vue'
import Login from './views/Login.vue'
import UserManagement from './views/UserManagement.vue'
import Accounts from './views/Accounts.vue'
import FileConfigs from './views/FileConfigs.vue'
import FileLists from './views/FileLists.vue'
import Projects from './views/Projects.vue'
import RoleManagement from './views/RoleManagement.vue'
import Forbidden from './views/Forbidden.vue'
import FileAudit from './views/FileAudit.vue'
import OperationAudit from './views/OperationAudit.vue'
import Settings from './views/Settings.vue'
import { clearAuth } from './api'
import { authUser, refreshAuth } from './composables/useAuth'
import { refreshSettings } from './composables/useSettings'
import { canVisit, landingPage } from './features/access/model'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', component: Dashboard, meta: { title: '概览' } },
    { path: '/users', component: UserManagement, meta: { title: '用户管理' } },
    { path: '/roles', component: RoleManagement, meta: { title: '角色管理' } },
    { path: '/forbidden', component: Forbidden, meta: { title: '无访问权限' } },
    { path: '/accounts', component: Accounts, meta: { title: '账号管理' } },
    { path: '/file-configs', component: FileConfigs, meta: { title: '文件管理' } },
    { path: '/file-lists', component: FileLists, meta: { title: '文件列表' } },
    { path: '/projects', component: Projects, meta: { title: '项目管理' } },
    { path: '/file-audits', component: FileAudit, meta: { title: '文件审计' } },
    { path: '/operation-audits', component: OperationAudit, meta: { title: '操作审计' } },
    { path: '/settings', component: Settings, meta: { title: '系统设置' } },
    { path: '/:pathMatch(.*)*', component: ModulePage },
  ],
})

router.beforeEach(async (to) => {
  const token = localStorage.getItem('confighub_token')
  if (to.path !== '/login' && !token) return '/login'
  if (!token) return true
  try { await refreshAuth() } catch { authUser.value = null; clearAuth(); return to.path === '/login' ? true : '/login' }
  try { await refreshSettings() } catch { /* appearance should not block navigation */ }
  if (to.path === '/login') return landingPage(authUser.value)
  if (to.path === '/' && !canVisit(authUser.value, '/')) return landingPage(authUser.value)
  if (!canVisit(authUser.value, to.path)) return '/forbidden'
})

const app = createApp(App)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) app.component(key, component)
app.use(router).use(ElementPlus).mount('#app')
