<template>
  <div class="page dashboard">
    <div class="page-heading">
      <div><div class="eyebrow">系统总览</div><h1>概览</h1><p>查看 FileHub 服务端与业务资源的实时状态。</p></div>
      <div class="dashboard-heading-actions">
        <span v-if="lastUpdated" class="dashboard-updated">更新于 {{ lastUpdated }}</span>
        <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新数据</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" class="api-note" :title="errorMessage" type="error" :closable="false" show-icon />

    <el-skeleton v-if="!data && loading" :rows="8" animated />
    <el-empty v-else-if="!data" description="暂无概览数据" :image-size="72" />
    <template v-else-if="data">
      <section class="server-banner">
        <div class="server-identity">
          <div class="server-icon"><el-icon><Monitor /></el-icon></div>
          <div>
            <div class="server-name">{{ data.server.name }} <span class="status-pill"><i></i>运行中</span></div>
            <div class="server-meta">
              <span><el-icon><Location /></el-icon>{{ data.server.address }}</span>
              <span><el-icon><Platform /></el-icon>{{ data.server.os }}</span>
              <span><el-icon><Timer /></el-icon>运行 {{ data.server.uptime }}</span>
            </div>
          </div>
        </div>
        <div class="live-indicator"><i></i><span>每 10 秒自动刷新</span></div>
      </section>

      <section class="metrics-grid">
        <article v-for="metric in data.metrics" :key="metric.key" class="metric-panel">
          <div class="metric-top"><span>{{ metric.label }}</span><span class="metric-icon" :style="{ color: metric.color, background: `${metric.color}14` }"><el-icon><component :is="metricIcons[metric.key]" /></el-icon></span></div>
          <div class="metric-value">{{ metric.value }}<small>{{ metric.unit }}</small></div>
          <div class="metric-foot"><span class="metric-detail">{{ metric.detail }}</span><span v-if="metric.percentage !== null">{{ metric.percentage }}%</span></div>
          <el-progress v-if="metric.percentage !== null" :percentage="metric.percentage" :show-text="false" :stroke-width="4" :color="metric.color" />
        </article>
      </section>

      <div class="dashboard-columns">
        <section class="panel monitor-panel">
          <div class="panel-heading"><div><h2>资源监控</h2><p>当前服务端 CPU 与内存使用趋势</p></div><el-radio-group v-model="chartRange" size="small"><el-radio-button value="5m">近 5 分钟</el-radio-button><el-radio-button value="15m">近 15 分钟</el-radio-button></el-radio-group></div>
          <div class="chart-legend"><span><i class="legend-blue"></i>CPU 使用率</span><span><i class="legend-green"></i>内存使用率</span><span class="legend-unit">使用率 (%)</span></div>
          <v-chart class="chart" :option="chartOption" autoresize />
        </section>
        <section class="panel quick-panel">
          <div class="panel-heading"><div><h2>快捷入口</h2><p>当前账号可访问的常用功能</p></div></div>
          <div class="quick-grid">
            <router-link v-for="item in quickLinks" :key="item.label" :to="item.path" class="quick-link">
              <span class="quick-icon" :style="{ color: item.color, background: item.bg }"><el-icon><component :is="item.icon" /></el-icon></span>
              <span>{{ item.label }}</span><el-icon class="quick-arrow"><ArrowRight /></el-icon>
            </router-link>
          </div>
          <el-empty v-if="!quickLinks.length" description="暂无可访问功能" :image-size="48" />
        </section>
      </div>

      <div class="dashboard-columns lower-columns">
        <section class="panel resources-panel">
          <div class="panel-heading"><div><h2>业务资源</h2><p>数据库中的实时资源数量</p></div></div>
          <div class="resource-table">
            <router-link v-for="resource in visibleResources" :key="resource.key" :to="resource.path" class="resource-row">
              <span class="resource-icon"><el-icon><component :is="resourceIcons[resource.key]" /></el-icon></span>
              <span class="resource-copy"><strong>{{ resource.label }}</strong><small>{{ resource.description }}</small></span>
              <b>{{ resource.count }}</b><el-icon><ArrowRight /></el-icon>
            </router-link>
          </div>
          <el-empty v-if="!visibleResources.length" description="暂无可查看的业务资源" :image-size="48" />
        </section>
        <section class="panel activity-panel">
          <div class="panel-heading"><div><h2>最近动态</h2><p>系统近期成功操作记录</p></div><router-link v-if="canAccess('/operation-audits')" to="/operation-audits" class="panel-more">查看全部 <el-icon><ArrowRight /></el-icon></router-link></div>
          <div v-if="data.activity.length" class="activity-list">
            <div v-for="item in data.activity" :key="item.id" class="activity-item">
              <span class="activity-mark" :class="item.type"><i></i></span>
              <div class="activity-copy"><strong>{{ item.title }}</strong><small>{{ item.operator }} · {{ item.detail }}</small></div><time>{{ formatActivityTime(item.occurred_at) }}</time>
            </div>
          </div>
          <el-empty v-else :description="canAccess('/operation-audits') ? '暂无操作记录' : '无操作审计查看权限'" :image-size="48" />
        </section>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ArrowRight, Collection, Connection, Cpu, DataLine, Files, FolderOpened, Key, List, Location, Monitor, Platform, Refresh, Timer } from '@element-plus/icons-vue'
import { api, type DashboardData } from '../api'
import { canAccess } from '../composables/useAuth'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const loading = ref(false)
const errorMessage = ref('')
const data = ref<DashboardData | null>(null)
const chartRange = ref<'5m' | '15m'>('5m')
let refreshTimer: ReturnType<typeof setInterval> | undefined

const metricIcons: Record<string, unknown> = { cpu: Cpu, memory: DataLine, disk: Files, network: Connection }
const resourceIcons: Record<string, unknown> = { projects: Collection, accounts: Key, configs: FolderOpened, files: List }
const allQuickLinks = [
  { label: '项目管理', path: '/projects', icon: Collection, color: '#3478d4', bg: '#eaf2ff' },
  { label: '账号管理', path: '/accounts', icon: Key, color: '#19a974', bg: '#e6f7f0' },
  { label: '文件管理', path: '/file-configs', icon: FolderOpened, color: '#d9902f', bg: '#fff4df' },
  { label: '文件列表', path: '/file-lists', icon: List, color: '#8062cc', bg: '#f0ebff' },
]
const quickLinks = computed(() => allQuickLinks.filter(item => canAccess(item.path)))
const visibleResources = computed(() => (data.value?.resources || []).filter(item => canAccess(item.path)))
const lastUpdated = computed(() => data.value ? new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(data.value.sampled_at)) : '')

const chartOption = computed(() => {
  const chart = data.value?.chart
  const count = chartRange.value === '5m' ? 30 : 90
  const labels = chart?.labels.slice(-count) || []
  const cpu = chart?.cpu.slice(-count) || []
  const memory = chart?.memory.slice(-count) || []
  return {
    animationDuration: 350,
    grid: { left: 48, right: 18, top: 15, bottom: 32 },
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#e7eaf0', textStyle: { color: '#303642' } },
    xAxis: { type: 'category', boundaryGap: false, data: labels, axisLine: { lineStyle: { color: '#e9edf2' } }, axisTick: { show: false }, axisLabel: { color: '#98a0ad', fontSize: 12, hideOverlap: true } },
    yAxis: { type: 'value', min: 0, max: 100, splitNumber: 4, axisLabel: { color: '#98a0ad', fontSize: 12, formatter: '{value}%' }, splitLine: { lineStyle: { color: '#f0f2f5', type: 'dashed' } } },
    series: [
      { name: 'CPU 使用率', type: 'line', smooth: true, showSymbol: cpu.length === 1, data: cpu, lineStyle: { width: 2.5, color: '#4388e8' }, itemStyle: { color: '#4388e8' }, areaStyle: { color: 'rgba(67,136,232,.08)' } },
      { name: '内存使用率', type: 'line', smooth: true, showSymbol: memory.length === 1, data: memory, lineStyle: { width: 2.5, color: '#39b77a' }, itemStyle: { color: '#39b77a' }, areaStyle: { color: 'rgba(57,183,122,.05)' } },
    ],
  }
})

function formatActivityTime(value: string) {
  const date = new Date(value)
  const today = new Date()
  const sameDay = date.toDateString() === today.toDateString()
  return new Intl.DateTimeFormat('zh-CN', sameDay
    ? { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }
    : { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(date)
}

async function loadData() {
  if (loading.value) return
  loading.value = true
  try {
    const response = await api.get<DashboardData>('/dashboard/')
    data.value = response.data
    errorMessage.value = ''
  } catch {
    errorMessage.value = data.value ? '实时数据刷新失败，当前显示最后一次成功获取的数据。' : '实时数据加载失败，请检查后端服务。'
  } finally {
    loading.value = false
  }
}

function handleVisibilityChange() {
  if (!document.hidden) loadData()
}

onMounted(() => {
  loadData()
  refreshTimer = setInterval(() => { if (!document.hidden) loadData() }, 10_000)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>
