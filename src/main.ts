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
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', component: Dashboard, meta: { title: '概览' } },
    { path: '/users', component: UserManagement, meta: { title: '用户管理' } },
    { path: '/accounts', component: Accounts, meta: { title: '账号管理' } },
    { path: '/file-configs', component: FileConfigs, meta: { title: '文件管理' } },
    { path: '/file-lists', component: FileLists, meta: { title: '文件列表' } },
    { path: '/projects', component: Projects, meta: { title: '项目管理' } },
    { path: '/:pathMatch(.*)*', component: ModulePage },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('confighub_token')
  if (to.path !== '/login' && !token) return '/login'
  if (to.path === '/login' && token) return '/'
})

const app = createApp(App)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) app.component(key, component)
app.use(router).use(ElementPlus).mount('#app')
