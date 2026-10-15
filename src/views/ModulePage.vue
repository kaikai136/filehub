<template>
  <div class="page module-page">
    <div class="page-heading">
      <div><div class="eyebrow">资源管理</div><h1>{{ title }}</h1><p>{{ description }}</p></div>
      <el-button type="primary" :icon="Plus" @click="createDialog = true">新建{{ title }}</el-button>
    </div>
    <div class="module-toolbar">
      <el-input v-model="query" :prefix-icon="Search" placeholder="搜索名称" clearable />
      <el-select v-model="status" placeholder="全部状态" clearable><el-option label="运行中" value="running" /><el-option label="已停止" value="stopped" /></el-select>
      <span class="toolbar-count">共 {{ filteredItems.length }} 项</span>
    </div>
    <div v-if="filteredItems.length" class="resource-list">
      <div v-for="item in filteredItems" :key="item.name" class="resource-row">
        <div class="resource-main"><span class="resource-avatar"><el-icon><component :is="item.icon" /></el-icon></span><div><strong>{{ item.name }}</strong><small>{{ item.detail }}</small></div></div>
        <el-tag :type="item.running ? 'success' : 'info'" effect="plain" size="small">{{ item.running ? '运行中' : '已停止' }}</el-tag>
        <span class="resource-updated">{{ item.updated }}</span>
        <el-button text :icon="MoreFilled" />
      </div>
    </div>
    <el-empty v-else description="没有找到匹配的资源" />
    <el-dialog v-model="createDialog" :title="`新建${title}`" width="440px">
      <el-form label-position="top"><el-form-item label="名称"><el-input v-model="newName" placeholder="请输入资源名称" /></el-form-item><el-form-item label="备注"><el-input placeholder="可选" /></el-form-item></el-form>
      <template #footer><el-button @click="createDialog = false">取消</el-button><el-button type="primary" :disabled="!newName.trim()" @click="createItem">创建</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Box, Coin, Connection, Document, Files, Monitor, MoreFilled, Plus, Search, Setting } from '@element-plus/icons-vue'

const route = useRoute()
const query = ref('')
const status = ref('')
const createDialog = ref(false)
const newName = ref('')
const configs: Record<string, { title: string; description: string; icon: unknown; items: { name: string; detail: string; running: boolean; updated: string; icon: unknown }[] }> = {
  containers: { title: '容器', description: '管理容器实例、镜像与运行状态。', icon: Box, items: [
    { name: 'nginx-proxy', detail: 'nginx:1.26-alpine · 80:80', running: true, updated: '刚刚', icon: Box },
    { name: 'redis-cache', detail: 'redis:7.4 · 6379:6379', running: true, updated: '12 分钟前', icon: Box },
    { name: 'worker-preview', detail: 'python:3.12-slim · 未配置端口', running: false, updated: '昨天', icon: Box },
    { name: 'postgres-main', detail: 'postgres:16 · 5432:5432', running: true, updated: '3 天前', icon: Box },
  ] },
  websites: { title: '网站', description: '管理网站、域名与反向代理配置。', icon: Monitor, items: [
    { name: '控制台', detail: 'console.example.com · HTTPS', running: true, updated: '刚刚', icon: Monitor },
    { name: '文档站点', detail: 'docs.example.com · HTTPS', running: true, updated: '今天 09:42', icon: Monitor },
    { name: '内部服务', detail: 'internal.example.com · HTTP', running: false, updated: '昨天', icon: Monitor },
  ] },
  databases: { title: '数据库', description: '管理数据库实例与连接信息。', icon: Coin, items: [
    { name: 'mysql-primary', detail: 'MySQL 8.0 · 127.0.0.1:3306', running: true, updated: '刚刚', icon: Coin },
    { name: 'redis-cache', detail: 'Redis 7.4 · 127.0.0.1:6379', running: true, updated: '今天 08:30', icon: Coin },
  ] },
  files: { title: '文件', description: '浏览和管理服务器文件。', icon: Files, items: [
    { name: '/opt/configHub', detail: '项目目录 · 24 个文件', running: true, updated: '刚刚', icon: Files },
    { name: '/var/www', detail: '网站目录 · 8 个站点', running: true, updated: '今天 10:15', icon: Files },
    { name: '/var/backups', detail: '备份目录 · 12 个归档', running: true, updated: '昨天', icon: Files },
  ] },
  monitor: { title: '监控', description: '查看主机资源与服务运行情况。', icon: Setting, items: [
    { name: '主机资源', detail: 'CPU 32% · 内存 43% · 磁盘 42%', running: true, updated: '实时', icon: Setting },
    { name: '服务健康检查', detail: '4 项服务 · 全部正常', running: true, updated: '1 分钟前', icon: Connection },
  ] },
  tasks: { title: '计划任务', description: '自动化管理定时任务。', icon: Setting, items: [
    { name: '每日数据库备份', detail: '每天 02:00 · /var/backups', running: true, updated: '下次运行 02:00', icon: Setting },
    { name: '清理临时文件', detail: '每周日 03:00', running: true, updated: '下次运行 周日', icon: Setting },
  ] },
  terminal: { title: '终端', description: '已连接到本机节点。', icon: Connection, items: [
    { name: '本机终端', detail: '192.168.1.100 · SSH 已就绪', running: true, updated: '在线', icon: Connection },
  ] },
  logs: { title: '操作日志', description: '查看近期系统操作与审计记录。', icon: Document, items: [
    { name: '服务重载', detail: '管理员 · Nginx 配置重载成功', running: true, updated: '10:42:18', icon: Document },
    { name: '配置更新', detail: '管理员 · 修改网站反向代理', running: true, updated: '09:36:05', icon: Document },
    { name: '安全检查', detail: '系统 · 未发现风险项', running: true, updated: '08:15:32', icon: Document },
  ] },
  settings: { title: '设置', description: '管理控制台偏好与节点配置。', icon: Setting, items: [
    { name: '基础设置', detail: '语言、时区与界面偏好', running: true, updated: '控制台', icon: Setting },
    { name: '节点设置', detail: '主机连接与节点信息', running: true, updated: 'config-hub-01', icon: Connection },
  ] },
}
const config = computed(() => configs[route.path.split('/')[1]] || configs.containers)
const title = computed(() => config.value.title)
const description = computed(() => config.value.description)
const items = ref(config.value.items.map((item) => ({ ...item })))
const filteredItems = computed(() => items.value.filter((item) =>
  item.name.toLowerCase().includes(query.value.toLowerCase()) &&
  (!status.value || item.running === (status.value === 'running')),
))
function createItem() {
  items.value.unshift({ name: newName.value.trim(), detail: '新建资源', running: false, updated: '刚刚', icon: config.value.icon })
  newName.value = ''
  createDialog.value = false
}
</script>
