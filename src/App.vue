<template>
  <router-view v-if="route.path === '/login'" />
  <div v-else class="shell">
    <aside class="sidebar" :class="{ collapsed }">
      <div class="brand"><div class="brand-mark"><el-icon><Grid /></el-icon></div><span v-if="!collapsed" class="brand-name">ConfigHub</span></div>
      <div v-if="!collapsed" class="node-switch"><span class="node-dot"></span><div class="node-copy"><strong>本机节点</strong><small>192.168.1.100</small></div><el-icon class="node-arrow"><ArrowDown /></el-icon></div>
      <el-scrollbar class="menu-scroll"><div v-for="group in groups" :key="group.title" class="menu-group"><div v-if="!collapsed" class="group-title">{{ group.title }}</div><router-link v-for="item in group.items" :key="item.path" :to="item.path" class="menu-item" :class="{ active: route.path === item.path }" :title="collapsed ? item.label : ''"><el-icon><component :is="item.icon" /></el-icon><span v-if="!collapsed">{{ item.label }}</span></router-link></div></el-scrollbar>
      <div class="sidebar-bottom"><router-link to="/settings" class="menu-item" :class="{ active: route.path === '/settings' }"><el-icon><Setting /></el-icon><span v-if="!collapsed">设置</span></router-link><button class="collapse-button" @click="collapsed = !collapsed"><el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon><span v-if="!collapsed">收起菜单</span></button><div v-if="!collapsed" class="sidebar-version"><span>ConfigHub</span><span>v1.0.0</span></div></div>
    </aside>
    <main class="main-area"><header class="topbar"><div class="breadcrumb"><span>控制台</span><el-icon><ArrowRight /></el-icon><strong>{{ pageTitle }}</strong></div><div class="top-actions"><el-input v-model="search" class="global-search" placeholder="搜索功能..." :prefix-icon="Search" /><el-tooltip content="帮助"><button class="icon-button"><el-icon><QuestionFilled /></el-icon></button></el-tooltip><el-tooltip content="通知"><button class="icon-button notification"><el-icon><Bell /></el-icon><i></i></button></el-tooltip><div class="user-menu" role="button" tabindex="0" title="退出登录" @click="logout"><el-avatar :size="30" style="background:#e8f1ff;color:#3478d4">K</el-avatar><span>管理员</span><el-icon><ArrowDown /></el-icon></div></div></header><section class="content-area"><router-view /></section><footer class="app-footer"><span>ConfigHub 运维控制台</span><span>系统运行正常 <i class="online-dot"></i></span></footer></main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { HomeFilled, Files, Document, DataLine, Setting, Expand, Fold, ArrowDown, ArrowRight, Search, QuestionFilled, Bell, Grid, Key, FolderOpened, List, Collection } from '@element-plus/icons-vue'
import { api, clearAuth } from './api'
const route = useRoute(); const router = useRouter(); const collapsed = ref(false); const search = ref('')
const groups = [
  { title: '总览', items: [{ label: '概览', path: '/', icon: HomeFilled }] },
  { title: '资源管理', items: [{ label: '项目管理', path: '/projects', icon: Collection }, { label: '账号管理', path: '/accounts', icon: Key }, { label: '文件管理', path: '/file-configs', icon: FolderOpened }, { label: '文件列表', path: '/file-lists', icon: List }] },
  { title: '运维', items: [{ label: '监控', path: '/monitor', icon: DataLine }, { label: '计划任务', path: '/tasks', icon: Document }, { label: '操作日志', path: '/logs', icon: Files }] },
  { title: '系统', items: [{ label: '用户管理', path: '/users', icon: Setting }] },
]
const titles: Record<string, string> = { '/': '概览', '/projects': '项目管理', '/accounts': '账号管理', '/file-configs': '文件管理', '/file-lists': '文件列表', '/monitor': '监控', '/tasks': '计划任务', '/logs': '操作日志', '/users': '用户管理', '/settings': '设置' }
const pageTitle = computed(() => titles[route.path] || '资源管理')
async function logout() { try { await api.post('/auth/logout/') } catch { /* token may already be expired */ } clearAuth(); ElMessage.success('已退出登录'); router.push('/login') }
</script>
