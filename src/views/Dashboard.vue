<template>
  <div class="page dashboard">
    <div class="page-heading">
      <div><div class="eyebrow">系统总览</div><h1>概览</h1><p>欢迎回来，查看服务器运行状态与资源使用情况。</p></div>
      <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新数据</el-button>
    </div>

    <section class="server-banner">
      <div class="server-identity">
        <div class="server-icon"><el-icon><Monitor /></el-icon></div>
        <div><div class="server-name">{{ data?.server.name || 'config-hub-01' }} <span class="status-pill"><i></i>运行中</span></div>
          <div class="server-meta"><span><el-icon><Location /></el-icon>{{ data?.server.address || '192.168.1.100' }}</span><span><el-icon><Platform /></el-icon>{{ data?.server.os || 'Ubuntu 24.04 LTS' }}</span><span><el-icon><Timer /></el-icon>运行 {{ data?.server.uptime || '12 天 8 小时' }}</span></div>
        </div>
      </div>
      <div class="banner-actions"><el-button text :icon="Connection">终端</el-button><el-button text :icon="Setting">节点设置</el-button></div>
    </section>

    <section class="metrics-grid">
      <article v-for="metric in metrics" :key="metric.key" class="metric-panel">
        <div class="metric-top"><span>{{ metric.label }}</span><span class="metric-icon" :style="{ color: metric.color, background: `${metric.color}14` }"><el-icon><component :is="metricIcons[metric.key]" /></el-icon></span></div>
        <div class="metric-value">{{ metric.value }}<small>{{ metric.unit }}</small></div>
        <div class="metric-foot"><span class="metric-spark" :style="{ color: metric.color }">▂ ▄ ▃ ▅ ▄ ▆ ▅ ▇</span><span>{{ metric.trend }}</span></div>
        <el-progress v-if="metric.key === 'cpu' || metric.key === 'disk'" :percentage="Number(metric.value)" :show-text="false" :stroke-width="4" :color="metric.color" />
      </article>
    </section>

    <div class="dashboard-columns">
      <section class="panel monitor-panel">
        <div class="panel-heading"><div><h2>资源监控</h2><p>服务器资源使用趋势</p></div><el-radio-group v-model="chartRange" size="small"><el-radio-button value="12h">12 小时</el-radio-button><el-radio-button value="24h">24 小时</el-radio-button></el-radio-group></div>
        <div class="chart-legend"><span><i class="legend-blue"></i>CPU 使用率</span><span><i class="legend-green"></i>内存使用率</span><span class="legend-unit">使用率 (%)</span></div>
        <v-chart class="chart" :option="chartOption" autoresize />
      </section>
      <section class="panel quick-panel">
        <div class="panel-heading"><div><h2>快捷入口</h2><p>常用管理功能</p></div><el-button text :icon="Setting" /></div>
        <div class="quick-grid">
          <router-link v-for="item in quickLinks" :key="item.label" :to="item.path" class="quick-link">
            <span class="quick-icon" :style="{ color: item.color, background: item.bg }"><el-icon><component :is="item.icon" /></el-icon></span>
            <span>{{ item.label }}</span><el-icon class="quick-arrow"><ArrowRight /></el-icon>
          </router-link>
        </div>
      </section>
    </div>

    <div class="dashboard-columns lower-columns">
      <section class="panel services-panel">
        <div class="panel-heading"><div><h2>系统服务</h2><p>当前节点运行中的服务</p></div><el-button text type="primary">管理服务 <el-icon><ArrowRight /></el-icon></el-button></div>
        <div class="service-table">
          <div class="service-row service-header"><span>服务名称</span><span>状态</span><span>版本</span><span></span></div>
          <div v-for="service in data?.services || fallbackServices" :key="service.name" class="service-row">
            <div class="service-name"><span class="service-icon" :style="{ background: service.color }"><el-icon><component :is="service.icon" /></el-icon></span><span><strong>{{ service.name }}</strong><small>{{ service.description }}</small></span></div>
            <span class="service-status"><i></i>{{ service.status }}</span><span class="service-version">{{ service.version }}</span><el-button text :icon="MoreFilled" />
          </div>
        </div>
      </section>
      <section class="panel activity-panel">
        <div class="panel-heading"><div><h2>最近动态</h2><p>系统近期操作记录</p></div><el-button text :icon="MoreFilled" /></div>
        <div class="activity-list">
          <div v-for="item in data?.activity || []" :key="item.time" class="activity-item">
            <span class="activity-mark" :class="item.type"><i></i></span>
            <div class="activity-copy"><strong>{{ item.title }}</strong><small>{{ item.detail }}</small></div><time>{{ item.time }}</time>
          </div>
          <div v-if="!data?.activity" v-for="item in fallbackActivity" :key="item.time" class="activity-item"><span class="activity-mark success"><i></i></span><div class="activity-copy"><strong>{{ item.title }}</strong><small>{{ item.detail }}</small></div><time>{{ item.time }}</time></div>
        </div>
      </section>
    </div>
    <el-alert v-if="apiUnavailable" class="api-note" title="当前为预览数据，连接后端 API 失败。" type="info" :closable="false" show-icon />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ArrowRight, Box, Coin, Connection, Cpu, DataLine, Files, MoreFilled, Monitor, Refresh, Setting, Location, Platform, Timer } from '@element-plus/icons-vue'
import { api, type DashboardData } from '../api'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])
const loading = ref(false)
const apiUnavailable = ref(false)
const data = ref<DashboardData | null>(null)
const chartRange = ref('12h')
const fallbackServices = [
  { name: 'Nginx', description: 'Web 服务器', status: '运行中', version: '1.26.2', icon: 'Connection', color: '#e8f4ff' },
  { name: 'MySQL', description: '关系型数据库', status: '运行中', version: '8.0.40', icon: 'Coin', color: '#fff3e0' },
  { name: 'Docker', description: '容器引擎', status: '运行中', version: '27.3.1', icon: 'Box', color: '#e8f7ef' },
]
const fallbackActivity = [
  { title: '系统服务启动完成', detail: 'Nginx 服务已启动', time: '10:42:18' },
  { title: '配置文件已更新', detail: 'nginx.conf 配置已保存', time: '09:36:05' },
  { title: '系统安全检查', detail: '未发现风险项', time: '08:15:32' },
]
const metrics = computed(() => data.value?.metrics || [
  { key: 'cpu', label: 'CPU 使用率', value: 32, unit: '%', color: '#409eff', trend: '+2.4%' },
  { key: 'memory', label: '内存使用', value: 6.8, unit: ' / 16 GB', color: '#67c23a', trend: '-0.8 GB' },
  { key: 'disk', label: '磁盘空间', value: 42, unit: '%', color: '#e6a23c', trend: '128 / 500 GB' },
  { key: 'network', label: '网络流量', value: 18.6, unit: ' MB/s', color: '#f56c6c', trend: '↑ 12.4  ↓ 6.2' },
])
const metricIcons: Record<string, unknown> = { cpu: Cpu, memory: DataLine, disk: Files, network: Connection }
const quickLinks = [
  { label: '容器管理', path: '/containers', icon: Box, color: '#3478d4', bg: '#eaf2ff' },
  { label: '网站管理', path: '/websites', icon: Monitor, color: '#19a974', bg: '#e6f7f0' },
  { label: '数据库', path: '/databases', icon: Coin, color: '#e09b27', bg: '#fff4df' },
  { label: '文件管理', path: '/files', icon: Files, color: '#8062cc', bg: '#f0ebff' },
]
const chartOption = computed(() => {
  const labels = data.value?.chart.labels || ['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00']
  const cpu = data.value?.chart.cpu || [22, 28, 25, 34, 31, 42, 36, 29, 33, 27, 35, 32]
  const memory = data.value?.chart.memory || [41, 43, 42, 44, 43, 46, 45, 44, 43, 45, 44, 43]
  return {
    animationDuration: 500,
    grid: { left: 50, right: 20, top: 15, bottom: 34 },
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#e7eaf0', textStyle: { color: '#303642' } },
    xAxis: { type: 'category', boundaryGap: false, data: labels, axisLine: { lineStyle: { color: '#e9edf2' } }, axisTick: { show: false }, axisLabel: { color: '#98a0ad', fontSize: 15 } },
    yAxis: { type: 'value', min: 0, max: 100, splitNumber: 4, axisLabel: { color: '#98a0ad', fontSize: 15, formatter: '{value}%' }, splitLine: { lineStyle: { color: '#f0f2f5', type: 'dashed' } } },
    series: [
      { name: 'CPU 使用率', type: 'line', smooth: true, showSymbol: false, data: cpu, lineStyle: { width: 2.5, color: '#4388e8' }, areaStyle: { color: 'rgba(67,136,232,.08)' } },
      { name: '内存使用率', type: 'line', smooth: true, showSymbol: false, data: memory, lineStyle: { width: 2.5, color: '#39b77a' }, areaStyle: { color: 'rgba(57,183,122,.05)' } },
    ],
  }
})
async function loadData() {
  loading.value = true
  try {
    const response = await api.get<DashboardData>('/dashboard/')
    data.value = response.data
    apiUnavailable.value = false
  } catch {
    apiUnavailable.value = true
  } finally {
    loading.value = false
  }
}
onMounted(loadData)
</script>
