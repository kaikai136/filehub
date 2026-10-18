<template>
  <div class="page audit-page">
    <div class="page-heading"><div><div class="eyebrow">运维</div><h1>文件审计</h1><p>查看远程文件的内容变更记录。</p></div><el-button :icon="Refresh" :loading="loading" @click="load" class="icon-primary">刷新</el-button></div>
    <div class="audit-filters">
      <el-date-picker v-model="filters.time" type="datetimerange" value-format="YYYY-MM-DDTHH:mm:ss" start-placeholder="开始时间" end-placeholder="结束时间" />
      <el-input v-model="filters.project" placeholder="项目名" clearable />
      <el-input v-model="filters.ip" placeholder="IP 地址" clearable />
      <el-input v-model="filters.directory" placeholder="文件目录" clearable />
      <el-input v-model="filters.operator" placeholder="操作人" clearable @keyup.enter="search" />
      <el-button type="primary" :icon="Search" @click="search" class="icon-primary">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="records" class="admin-table" v-loading="loading" empty-text="暂无文件审计记录">
      <el-table-column prop="project_name" label="项目名" min-width="150" show-overflow-tooltip />
      <el-table-column prop="ip_address" label="IP 地址" min-width="140" />
      <el-table-column prop="directory" label="文件目录" min-width="280" show-overflow-tooltip />
      <el-table-column label="操作人" min-width="140"><template #default="{ row }">{{ row.operator.name }}</template></el-table-column>
      <el-table-column label="更改时间" min-width="180"><template #default="{ row }">{{ formatDate(row.changed_at) }}</template></el-table-column>
      <el-table-column label="查看" width="82" fixed="right"><template #default="{ row }"><el-tooltip content="查看变更"><el-button text :icon="View" aria-label="查看文件变更" @click="showDiff(row)" class="icon-primary" /></el-tooltip></template></el-table-column>
    </el-table>
    <div class="audit-pagination"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next" @current-change="load" @size-change="page = 1; load()" /></div>
    <el-dialog v-model="diffVisible" width="82%" top="5vh" :title="selected?.directory || '文件变更'">
      <div class="diff-summary"><span>{{ selected?.project_name }}</span><span>{{ selected?.ip_address }}</span><span>{{ selected ? formatDate(selected.changed_at) : '' }}</span></div>
      <div class="diff-viewer" v-loading="detailLoading">
        <div v-for="(line, index) in diffLines" :key="index" class="diff-line" :class="`is-${line.kind}`"><span class="diff-number">{{ index + 1 }}</span><pre>{{ line.text || ' ' }}</pre></div>
        <el-empty v-if="!detailLoading && !diffLines.length" description="没有可显示的差异" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search, View } from '@element-plus/icons-vue'
import { api } from '../api'
import { auditQuery, parseUnifiedDiff } from '../features/audit/model'

type Operator = { id: number | null; username: string; name: string }
type FileAudit = { id: number; project_name: string; project_id: number | null; ip_address: string; directory: string; relative_path: string; operator: Operator; changed_at: string; diff?: string }
type PageResult<T> = { count: number; page: number; page_size: number; results: T[] }
const records = ref<FileAudit[]>([]), total = ref(0), page = ref(1), pageSize = ref(20), loading = ref(false), error = ref('')
const filters = reactive({ time: [] as string[], project: '', ip: '', directory: '', operator: '' })
const selected = ref<FileAudit | null>(null), diffVisible = ref(false), detailLoading = ref(false)
const diffLines = computed(() => parseUnifiedDiff(selected.value?.diff || ''))
async function load() { loading.value = true; error.value = ''; try { const { data } = await api.get<PageResult<FileAudit>>('/file-audits/', { params: auditQuery(filters, page.value, pageSize.value) }); records.value = data.results; total.value = data.count } catch (e: any) { error.value = e.response?.data?.detail || '加载文件审计失败' } finally { loading.value = false } }
function search() { page.value = 1; void load() }
function reset() { Object.assign(filters, { time: [], project: '', ip: '', directory: '', operator: '' }); search() }
async function showDiff(record: FileAudit) { selected.value = { ...record }; diffVisible.value = true; detailLoading.value = true; try { selected.value = (await api.get<FileAudit>(`/file-audits/${record.id}/`)).data } catch (e: any) { ElMessage.error(e.response?.data?.detail || '加载文件差异失败'); diffVisible.value = false } finally { detailLoading.value = false } }
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN') }
onMounted(load)
</script>

<style scoped>
.audit-filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.audit-filters :deep(.el-input) { width: 160px; }
.audit-pagination { display: flex; justify-content: flex-end; padding-top: 16px; }
.diff-summary { display: flex; gap: 24px; margin-bottom: 12px; color: #68778b; font-size: 13px; flex-wrap: wrap; }
.diff-viewer { min-height: 340px; max-height: 68vh; overflow: auto; border: 1px solid #dfe5ec; background: #fff; font-family: Consolas, "Cascadia Code", monospace; font-size: 13px; }
.diff-line { display: grid; grid-template-columns: 54px minmax(max-content, 1fr); min-height: 23px; line-height: 23px; }
.diff-line pre { margin: 0; padding: 0 10px; white-space: pre; letter-spacing: 0; }
.diff-number { padding-right: 9px; border-right: 1px solid rgba(120,130,145,.2); color: #98a2af; text-align: right; user-select: none; }
.diff-line.is-added { background: #e8f6ec; color: #246b38; }
.diff-line.is-removed { background: #fdebec; color: #a12f37; }
.diff-line.is-hunk { background: #eef4fc; color: #41698f; }
.diff-line.is-meta { background: #f5f7fa; color: #526274; font-weight: 600; }
</style>
