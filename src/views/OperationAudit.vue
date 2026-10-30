<template>
  <div class="page audit-page">
    <div class="page-heading"><div><div class="eyebrow">运维</div><h1>操作审计</h1><p>查询系统关键操作记录。</p></div><el-button :icon="Refresh" :loading="loading" @click="load" class="icon-primary">刷新</el-button></div>
    <div class="audit-filters">
      <el-date-picker v-model="filters.time" type="datetimerange" value-format="YYYY-MM-DDTHH:mm:ss" start-placeholder="开始时间" end-placeholder="结束时间" />
      <el-input v-model="filters.operator" placeholder="操作人" clearable />
      <el-input v-model="filters.module" placeholder="模块" clearable />
      <el-input v-model="filters.action" placeholder="操作" clearable />
      <el-input v-model="filters.ip" placeholder="IP 地址" clearable />
      <el-button type="primary" :icon="Search" @click="search" class="icon-primary">查询</el-button><el-button @click="reset">重置</el-button>
      <el-button v-if="canDelete" type="danger" :disabled="!selectedIds.length || loading || actionLoading" @click="bulkDelete">删除所选{{ selectedIds.length ? ` (${selectedIds.length})` : '' }}</el-button>
      <el-button v-if="canDelete" type="danger" plain :disabled="loading || actionLoading" :loading="actionLoading" @click="clearAll">一键清空</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table ref="tableRef" :data="records" row-key="id" class="admin-table" v-loading="loading" empty-text="暂无操作审计记录" @selection-change="onSelectionChange">
      <el-table-column v-if="canDelete" type="selection" reserve-selection width="52" />
      <el-table-column label="时间" min-width="180"><template #default="{ row }">{{ formatDate(row.occurred_at) }}</template></el-table-column>
      <el-table-column label="操作人" min-width="140"><template #default="{ row }">{{ row.operator.name }}</template></el-table-column>
      <el-table-column prop="module" label="模块" min-width="120" />
      <el-table-column prop="action" label="操作" min-width="110" />
      <el-table-column prop="object" label="对象" min-width="180" show-overflow-tooltip />
      <el-table-column prop="ip_address" label="IP" min-width="140"><template #default="{ row }">{{ row.ip_address || '—' }}</template></el-table-column>
      <el-table-column label="详情" min-width="220"><template #default="{ row }"><div class="audit-detail-cell"><span>{{ row.detail || '—' }}</span><el-tooltip content="查看详情"><el-button text :icon="View" aria-label="查看操作详情" @click="showDetail(row)" class="icon-primary" /></el-tooltip></div></template></el-table-column>
    </el-table>
    <div class="audit-pagination"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next" @current-change="load" @size-change="page = 1; load()" /></div>
    <el-drawer v-model="detailVisible" title="操作详情" size="480px">
      <el-descriptions v-if="selected" :column="1" border>
        <el-descriptions-item label="时间">{{ formatDate(selected.occurred_at) }}</el-descriptions-item><el-descriptions-item label="操作人">{{ selected.operator.name }}</el-descriptions-item><el-descriptions-item label="模块">{{ selected.module }}</el-descriptions-item><el-descriptions-item label="操作">{{ selected.action }}</el-descriptions-item><el-descriptions-item label="对象">{{ selected.object || '—' }}</el-descriptions-item><el-descriptions-item label="IP">{{ selected.ip_address || '—' }}</el-descriptions-item><el-descriptions-item label="详情"><span class="detail-text">{{ selected.detail || '—' }}</span></el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type ElTable } from 'element-plus'
import { Refresh, Search, View } from '@element-plus/icons-vue'
import { api } from '../api'
import { hasPermission } from '../composables/useAuth'
import { auditQuery } from '../features/audit/model'
type Operator = { id: number | null; username: string; name: string }
type OperationAudit = { id: number; occurred_at: string; operator: Operator; module: string; action: string; object: string; ip_address: string | null; detail: string }
type PageResult<T> = { count: number; page: number; page_size: number; results: T[] }
const records = ref<OperationAudit[]>([]), total = ref(0), page = ref(1), pageSize = ref(20), loading = ref(false), error = ref('')
const filters = reactive({ time: [] as string[], operator: '', module: '', action: '', ip: '' })
const selected = ref<OperationAudit | null>(null), detailVisible = ref(false)
const selectedIds = ref<number[]>([]), actionLoading = ref(false), tableRef = ref<InstanceType<typeof ElTable>>()
const canDelete = computed(() => hasPermission('operation_audit.view') && hasPermission('operation_audit.delete'))
async function load() { loading.value = true; error.value = ''; try { const { data } = await api.get<PageResult<OperationAudit>>('/operation-audits/', { params: auditQuery(filters, page.value, pageSize.value) }); records.value = data.results; total.value = data.count } catch (e: any) { error.value = e.response?.data?.detail || '加载操作审计失败' } finally { loading.value = false } }
function search() { page.value = 1; void load() }
function reset() { Object.assign(filters, { time: [], operator: '', module: '', action: '', ip: '' }); search() }
function onSelectionChange(rows: OperationAudit[]) { selectedIds.value = [...new Set(rows.map(row => row.id))] }
async function bulkDelete() { if (!canDelete.value || loading.value || actionLoading.value || !selectedIds.value.length) return; actionLoading.value = true; const ids = [...selectedIds.value]; try { await ElMessageBox.confirm(`确定删除选中的 ${ids.length} 条操作审计记录吗？（包含其他分页及查询条件下的已选记录）`, '删除确认', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }); let deletedCount = 0; for (let offset = 0; offset < ids.length; offset += 100) { const batch = ids.slice(offset, offset + 100); const { data } = await api.post('/operation-audits/bulk-delete/', { ids: batch }); deletedCount += data.deleted_count; const completed = new Set(batch); for (const row of tableRef.value?.getSelectionRows() || []) if (completed.has(row.id)) tableRef.value?.toggleRowSelection(row, false); selectedIds.value = selectedIds.value.filter(id => !completed.has(id)) } ElMessage.success(`已删除 ${deletedCount} 条记录`); await reloadAfterDelete() } catch (e: any) { if (e !== 'cancel' && e !== 'close') ElMessage.error(e.response?.data?.detail || '删除操作审计失败') } finally { actionLoading.value = false } }
async function clearAll() { if (!canDelete.value || loading.value || actionLoading.value) return; actionLoading.value = true; try { await ElMessageBox.confirm('将删除全部操作审计记录，不受筛选和分页限制，无法恢复。确定继续吗？', '一键清空确认', { type: 'warning', confirmButtonText: '全部清空', cancelButtonText: '取消' }); const { data } = await api.post('/operation-audits/clear/'); ElMessage.success(`已清空 ${data.deleted_count} 条记录`); tableRef.value?.clearSelection(); selectedIds.value = []; page.value = 1; await reloadAfterDelete() } catch (e: any) { if (e !== 'cancel' && e !== 'close') ElMessage.error(e.response?.data?.detail || '清空操作审计失败') } finally { actionLoading.value = false } }
async function reloadAfterDelete() { await load(); const lastPage = Math.max(1, Math.ceil(total.value / pageSize.value)); if (!error.value && page.value > lastPage) { page.value = lastPage; await load() } }
function showDetail(record: OperationAudit) { selected.value = record; detailVisible.value = true }
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN') }
onMounted(load)
</script>

<style scoped>
.audit-filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.audit-filters :deep(.el-input) { width: 145px; }
.audit-pagination { display: flex; justify-content: flex-end; padding-top: 16px; }
.audit-detail-cell { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-width: 0; }
.audit-detail-cell > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.detail-text { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
