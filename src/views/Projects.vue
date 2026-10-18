<template>
  <div ref="pageElement" class="page project-page" :class="{ 'project-fullscreen': fullscreen }">
    <div class="page-heading"><div><div class="eyebrow">资源管理</div><h1>项目管理</h1><p>按项目管理主机配置，验证连接并查看机器规格。</p></div><el-button :icon="Refresh" :loading="loading" @click="load" class="icon-primary">刷新列表</el-button></div>
    <div class="project-browser">
      <aside class="project-panel">
        <div class="project-panel-heading"><strong>项目列表</strong><el-button v-if="hasPermission('projects.create')" circle type="primary" :icon="Plus" title="新增项目" aria-label="新增项目" @click="editProject(null)" class="icon-success" /></div>
        <el-input v-model="projectSearch" :prefix-icon="Search" placeholder="搜索项目" clearable class="icon-primary" />
        <button class="all-projects" :class="{ active: selectedProject === null }" @click="selectProject(null)">全部项目 <span>{{ configs.length }}</span></button>
        <el-tree ref="treeRef" :data="tree" node-key="id" highlight-current default-expand-all :expand-on-click-node="false" :filter-node-method="filterProject" @node-click="(node: ProjectNode) => selectProject(node.id)">
          <template #default="{ data }"><span class="project-tree-label" :title="data.path"><el-icon class="icon-warning"><FolderOpened /></el-icon><span>{{ data.name }}</span><small>{{ data.count }}</small><el-dropdown v-if="hasPermission('projects.create') || hasPermission('projects.edit') || hasPermission('projects.delete')" trigger="click" @command="(command: string) => projectAction(command, data)"><el-button text :icon="MoreFilled" aria-label="项目操作" @click.stop class="icon-primary" /><template #dropdown><el-dropdown-menu><el-dropdown-item v-if="hasPermission('projects.create')" command="child">新增子项目</el-dropdown-item><el-dropdown-item v-if="hasPermission('projects.edit')" command="edit">重命名 / 移动 / 排序</el-dropdown-item><el-dropdown-item v-if="hasPermission('projects.delete')" command="delete" divided>删除空项目</el-dropdown-item></el-dropdown-menu></template></el-dropdown></span></template>
        </el-tree>
      </aside>
      <section class="project-content">
        <div class="project-content-heading"><div><h2>{{ selectedProjectName }}</h2><p>主机列表 · 包含子项目</p></div><el-tag effect="plain">{{ filtered.length }} 条配置</el-tag></div>
        <div class="project-toolbar">
          <el-input v-model="search" :prefix-icon="Search" clearable placeholder="节点名称 / 机器名称 / IP" aria-label="搜索主机" class="icon-primary" />
          <el-select v-model="status" clearable placeholder="全部状态" aria-label="筛选状态"><el-option label="已验证" value="success" /><el-option label="验证失败" value="error" /><el-option label="未验证" value="pending" /></el-select>
          <div class="project-toolbar-actions">
            <el-button v-if="hasPermission('projects.create')" type="primary" :icon="Plus" :disabled="busy" @click="openEditor(null)" class="icon-success">新建</el-button>
            <el-dropdown v-if="hasPermission('projects.execute') || hasPermission('projects.edit') || hasPermission('projects.delete')" :disabled="busy" @command="batchAction"><el-button :disabled="busy">更多操作<el-icon class="icon-primary"><ArrowDown /></el-icon></el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-if="hasPermission('projects.execute')" command="inspect" :disabled="!selected.length">验证并采集所选</el-dropdown-item><el-dropdown-item v-if="hasPermission('projects.edit')" command="move" :disabled="!selected.length">移动所选项目</el-dropdown-item><el-dropdown-item v-if="hasPermission('projects.delete')" command="delete" :disabled="!selected.length" divided>删除所选</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
            <el-button v-if="hasPermission('projects.import')" :icon="Upload" title="导入 Excel" aria-label="导入 Excel" :disabled="busy" @click="importDialog?.open()" class="icon-warning" />
            <el-dropdown v-if="hasPermission('projects.export')" @command="exportRows"><el-button :icon="Download" title="导出 Excel" aria-label="导出 Excel" class="icon-primary" /><template #dropdown><el-dropdown-menu><el-dropdown-item command="filtered">导出当前筛选范围</el-dropdown-item><el-dropdown-item command="selected" :disabled="!selected.length">导出勾选记录</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
            <el-button :icon="Refresh" title="刷新" aria-label="刷新" :loading="loading" @click="load" class="icon-primary" />
            <el-popover placement="bottom-end" :width="200" trigger="click"><template #reference><el-button :icon="Setting" title="列设置" aria-label="列设置" class="icon-primary" /></template><div class="project-column-options"><el-checkbox v-for="column in columns" :key="column.key" :model-value="visibleColumns.includes(column.key)" :disabled="visibleColumns.length === 1 && visibleColumns.includes(column.key)" @change="toggleColumn(column.key)">{{ column.label }}</el-checkbox><el-button text @click="visibleColumns = columns.map(c => c.key)">恢复默认</el-button></div></el-popover>
            <el-button :icon="FullScreen" :title="fullscreen ? '退出全屏' : '全屏'" aria-label="切换全屏" @click="fullscreen = !fullscreen" class="icon-primary" />
          </div>
        </div>
        <el-alert v-if="pageError" :title="pageError" type="error" :closable="false" />
        <div v-if="progress.total" class="project-progress"><span>处理进度：{{ progress.done }} / {{ progress.total }}</span><el-progress :percentage="Math.round(progress.done / progress.total * 100)" /></div>
        <div class="project-table-scroll">
          <el-table ref="tableRef" :data="paged" row-key="id" border v-loading="loading" empty-text="当前项目暂无匹配的主机配置" @selection-change="selectionChanged" @sort-change="sortChanged">
            <el-table-column v-if="hasPermission('projects.execute') || hasPermission('projects.edit') || hasPermission('projects.delete') || hasPermission('projects.export')" type="selection" width="40" reserve-selection :selectable="() => !busy" />
            <el-table-column v-for="column in shownColumns" :key="column.key" :prop="column.key" :label="column.label" :min-width="column.width" :fixed="column.key === 'actions' ? 'right' : undefined" :sortable="column.key === 'actions' || column.key === 'specifications' ? false : 'custom'">
              <template #default="{ row }">
                <div v-if="column.key === 'specifications'" class="project-spec"><span>规格：{{ row.specifications.cpu ? `${row.specifications.cpu}C` : '—' }} / {{ formatBytes(row.specifications.memory_bytes) }} / {{ formatBytes(row.specifications.disk_bytes) }}</span><span :title="`${row.specifications.system || ''} ${row.specifications.arch || ''}`">系统：{{ row.specifications.system || '—' }} · {{ row.specifications.arch || '—' }}</span><el-tooltip v-if="row.inspection_error" :content="row.inspection_error"><small class="project-warning">规格采集失败</small></el-tooltip></div>
                <el-tag v-else-if="column.key === 'platform_type' && row.platform_type" :type="row.platform_type === 'windows' ? 'primary' : 'success'" size="small">{{ row.platform_type }}</el-tag>
                <span v-else-if="column.key === 'updated_at'">{{ new Date(row.updated_at).toLocaleString('zh-CN') }}</span>
                <el-tooltip v-else-if="column.key === 'connection_status'" :content="row.connection_error || connectionText(row.connection_status)"><el-tag effect="plain" :type="row.connection_status === 'success' ? 'success' : row.connection_status === 'error' ? 'danger' : 'info'">{{ pending.has(row.id) ? '验证中…' : connectionText(row.connection_status) }}</el-tag></el-tooltip>
                <div v-else-if="column.key === 'actions'" class="project-row-actions"><el-button v-if="hasPermission('projects.edit')" text :icon="EditPen" title="编辑" aria-label="编辑主机" :disabled="busy" @click="openEditor(row)" class="icon-primary" /><el-button v-if="hasPermission('projects.execute')" text :icon="Refresh" title="验证并采集规格" aria-label="验证并采集规格" :loading="pending.has(row.id)" :disabled="busy" @click="inspectRows([row])" class="icon-primary" /><el-button v-if="hasPermission('projects.delete')" text type="danger" :icon="Delete" title="删除" aria-label="删除主机" :disabled="busy" @click="deleteRows([row])" class="icon-danger" /></div>
                <span v-else :title="String(row[column.key] || '')">{{ row[column.key] || '—' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <footer class="project-content-footer"><span>已选 {{ selected.length }} 条 · 每条主机配置独立展示</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50, 100]" :total="filtered.length" layout="total, sizes, prev, pager, next" /></footer>
      </section>
    </div>
    <ConfigEditor v-if="hasPermission('projects.create') || hasPermission('projects.edit')" v-model="editorVisible" :config="editing" :project-id="selectedProject" @saved="load" />
    <ImportDialog v-if="hasPermission('projects.import')" ref="importDialog" @imported="load" />
    <el-dialog v-model="projectDialog" :title="projectForm.id ? '编辑项目' : '新增项目'" width="460px" :close-on-click-modal="false" :before-close="(done: () => void) => { if (!projectSaving) done() }">
      <el-form label-position="top" :disabled="projectSaving"><el-form-item label="项目名称"><el-input v-model="projectForm.name" maxlength="150" /></el-form-item><el-form-item label="父项目（留空为顶层）"><el-tree-select v-model="projectForm.parent_id" :data="parentTree" node-key="id" clearable check-strictly filterable /></el-form-item><el-form-item label="排序值（小值在前）"><el-input-number v-model="projectForm.sort_order" :min="0" /></el-form-item><el-alert v-if="projectError" :title="projectError" type="error" :closable="false" /></el-form>
      <template #footer><el-button :disabled="projectSaving" @click="projectDialog = false">取消</el-button><el-button type="primary" :loading="projectSaving" @click="saveProject">保存</el-button></template>
    </el-dialog>
    <el-dialog v-model="moveDialog" title="移动所选配置到项目" width="420px" :close-on-click-modal="false" :before-close="(done: () => void) => { if (!busy) done() }"><el-tree-select v-model="moveTarget" :data="tree" node-key="id" check-strictly filterable /><template #footer><el-button :disabled="busy" @click="moveDialog = false">取消</el-button><el-button type="primary" :disabled="!moveTarget" :loading="busy" @click="moveRows">移动</el-button></template></el-dialog>
    <el-dialog v-model="resultsVisible" title="操作结果" width="640px"><p>成功 {{ results.filter(r => r.success).length }} 条，失败 {{ results.filter(r => !r.success).length }} 条</p><el-table :data="results" max-height="400"><el-table-column prop="name" label="节点" /><el-table-column label="结果"><template #default="{ row }">{{ row.success ? '成功' : '失败' }}</template></el-table-column><el-table-column prop="error" label="说明" min-width="260" /></el-table></el-dialog>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type ElTree } from 'element-plus'
import { ArrowDown, Delete, Download, EditPen, FolderOpened, FullScreen, MoreFilled, Plus, Refresh, Search, Setting, Upload } from '@element-plus/icons-vue'
import { api } from '../api'
import { hasPermission } from '../composables/useAuth'
import ConfigEditor from '../features/projects/ConfigEditor.vue'
import ImportDialog from '../features/projects/ImportDialog.vue'
import { columns, connectionText, descendantIds, errorText, filterHosts, formatBytes, pageHosts, projectTree, runLimited, sortHosts, type Config, type Project, type ProjectNode } from '../features/projects/model'
const configs = ref<Config[]>([]), projects = ref<Project[]>([]), selectedProject = ref<number | null>(null)
const tree = computed(() => projectTree(projects.value, configs.value)), treeRef = ref<InstanceType<typeof ElTree>>()
const projectSearch = ref(''), search = ref(''), status = ref(''), page = ref(1), pageSize = ref(10)
const loading = ref(false), busy = ref(false), pageError = ref(''), fullscreen = ref(false), pageElement = ref<HTMLElement>()
const filtered = computed(() => filterHosts(configs.value, projects.value, selectedProject.value, search.value, status.value))
const sort = reactive({ prop: '', descending: false })
const paged = computed(() => pageHosts(sort.prop ? sortHosts(filtered.value, sort.prop, sort.descending) : filtered.value, page.value, pageSize.value))
const selectedProjectName = computed(() => projects.value.find(p => p.id === selectedProject.value)?.path || '全部项目')
const tableRef = ref<{ clearSelection: () => void }>(), selected = ref<Config[]>([])
const pending = reactive(new Set<number>()), progress = reactive({ total: 0, done: 0 })
const results = ref<{ id: number; name: string; success: boolean; error?: string }[]>([]), resultsVisible = ref(false)
const visibleColumns = ref<string[]>(columns.map(c => c.key)), shownColumns = computed(() => columns.filter(c => visibleColumns.value.includes(c.key)))
const editorVisible = ref(false), editing = ref<Config | null>(null), importDialog = ref<InstanceType<typeof ImportDialog>>()
const projectDialog = ref(false), projectSaving = ref(false), projectError = ref('')
const projectForm = reactive({ id: null as number | null, name: '', parent_id: null as number | null, sort_order: 0 })
const parentTree = computed(() => projectTree(projects.value.filter(p => !projectForm.id || !descendantIds(projects.value, projectForm.id).has(p.id))))
const moveDialog = ref(false), moveTarget = ref<number>()
let loadVersion = 0
async function load() {
  const version = ++loadVersion; loading.value = true; pageError.value = ''
  try {
    const [p, c] = await Promise.all([api.get<Project[]>('/projects/'), api.get<Config[]>('/file-configs/', { params: { scope: 'hosts' } })])
    if (version !== loadVersion) return
    projects.value = p.data; configs.value = c.data
    if (selectedProject.value !== null && !projects.value.some(p => p.id === selectedProject.value)) selectedProject.value = null
    selected.value = []; tableRef.value?.clearSelection()
    await nextTick(); treeRef.value?.filter(projectSearch.value)
  } catch (e) { if (version === loadVersion) pageError.value = errorText(e) }
  finally { if (version === loadVersion) loading.value = false }
}
function filterProject(query: string, node: ProjectNode) { return node.path.toLowerCase().includes(query.trim().toLowerCase()) }
watch(projectSearch, value => treeRef.value?.filter(value))
function selectProject(id: number | null) { selectedProject.value = id; treeRef.value?.setCurrentKey(id ?? undefined) }
watch([selectedProject, search, status, pageSize], () => { page.value = 1; tableRef.value?.clearSelection(); selected.value = [] })
watch(() => filtered.value.length, length => { page.value = Math.min(page.value, Math.max(1, Math.ceil(length / pageSize.value))) })
function selectionChanged(rows: Config[]) { selected.value = rows }
function sortChanged(value: { prop: string; order: string | null }) { sort.prop = value.order ? value.prop : ''; sort.descending = value.order === 'descending'; page.value = 1 }
function toggleColumn(key: string) { visibleColumns.value = visibleColumns.value.includes(key) ? visibleColumns.value.filter(k => k !== key) : [...visibleColumns.value, key] }
function openEditor(row: Config | null) { editing.value = row ? { ...row } : null; editorVisible.value = true }
function editProject(row: Project | null, parent: number | null = null) { Object.assign(projectForm, row ? { ...row } : { id: null, name: '', parent_id: parent, sort_order: 0 }); projectError.value = ''; projectDialog.value = true }
async function saveProject() {
  if (projectSaving.value) return
  projectSaving.value = true; projectError.value = ''
  try {
    const payload = { name: projectForm.name, parent_id: projectForm.parent_id || null, sort_order: projectForm.sort_order }
    if (projectForm.id) await api.patch(`/projects/${projectForm.id}/`, payload); else await api.post('/projects/', payload)
    projectDialog.value = false; await load(); ElMessage.success('项目已保存')
  } catch (e) { projectError.value = errorText(e) }
  finally { projectSaving.value = false }
}
async function projectAction(command: string, node: Project) {
  if (command === 'child') return editProject(null, node.id)
  if (command === 'edit') return editProject(node)
  try { await ElMessageBox.confirm(`删除空项目“${node.name}”？`, '删除项目', { type: 'warning' }) } catch { return }
  try { await api.delete(`/projects/${node.id}/`); await load() } catch (e) { ElMessage.error(errorText(e)) }
}
async function inspectRows(rows: Config[]) {
  if (busy.value || !rows.length) return
  busy.value = true; results.value = []; progress.total = rows.length; progress.done = 0
  await runLimited([...rows], async row => {
    pending.add(row.id)
    try {
      const { data } = await api.post(`/file-configs/${row.id}/inspect/`, undefined, { timeout: 120000 })
      const current = configs.value.find(c => c.id === row.id)
      if (current && data.config.revision >= current.revision) Object.assign(current, data.config)
      results.value.push({ id: row.id, name: row.host_name, success: data.config.inspection_status === 'success', error: data.config.inspection_error ? `SSH 已验证；${data.config.inspection_error}` : '' })
    } catch (e: any) {
      const current = configs.value.find(c => c.id === row.id), incoming = e.response?.data?.config
      if (current && incoming && incoming.revision >= current.revision) Object.assign(current, incoming)
      results.value.push({ id: row.id, name: row.host_name, success: false, error: errorText(e) })
    } finally { pending.delete(row.id); progress.done++ }
  })
  busy.value = false; resultsVisible.value = true
}
async function executeBatch(action: 'delete' | 'move', rows: Config[], projectId?: number) {
  busy.value = true
  try {
    const { data } = await api.post('/file-configs/batch/', { action, items: rows.map(r => ({ id: r.id, revision: r.revision })), project_id: projectId }, { timeout: 60000 })
    results.value = data.results.map((r: { id: number; success: boolean; error?: string }) => ({ ...r, name: rows.find(row => row.id === r.id)?.host_name || String(r.id) }))
    resultsVisible.value = true; moveDialog.value = false; await load()
  } catch (e) { ElMessage.error(errorText(e)) }
  finally { busy.value = false }
}
async function deleteRows(rows: Config[]) {
  if (busy.value || !rows.length) return
  const targets = rows.map(row => ({ ...row }))
  try { await ElMessageBox.confirm(`删除 ${targets.length} 条主机配置？将同步删除文件管理配置和本地文件列表缓存，不删除远程真实文件。`, '确认删除', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }) } catch { return }
  await executeBatch('delete', targets)
}
function batchAction(command: string) { if (command === 'inspect') void inspectRows(selected.value); else if (command === 'delete') void deleteRows(selected.value); else { moveTarget.value = undefined; moveDialog.value = true } }
async function moveRows() { if (!busy.value && moveTarget.value) await executeBatch('move', [...selected.value], moveTarget.value) }
async function exportRows(scope: string) {
  try {
    const { data } = await api.post('/file-configs/export/', { ids: (scope === 'selected' ? selected.value : filtered.value).map(c => c.id) }, { responseType: 'blob', timeout: 60000 })
    const url = URL.createObjectURL(data), a = document.createElement('a'); a.href = url; a.download = '主机配置.xlsx'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) { ElMessage.error(errorText(e)) }
}
function escape(event: KeyboardEvent) { if (event.key === 'Escape') fullscreen.value = false }
onMounted(() => { void load(); window.addEventListener('keydown', escape) })
onBeforeUnmount(() => { loadVersion++; window.removeEventListener('keydown', escape) })
</script>
<style scoped>
.project-browser { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 16px; align-items: stretch; }
.project-panel, .project-content { min-width: 0; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; }
.project-panel { padding: 18px 12px; overflow: auto; }
.project-panel-heading { display: flex; align-items: center; justify-content: space-between; padding: 0 4px 16px; font-size: 16px; }
.project-tree-label { display: flex; align-items: center; gap: 7px; width: 100%; min-width: 0; }
.project-tree-label > span { overflow: hidden; text-overflow: ellipsis; }
.project-tree-label small { color: #8793a1; margin-left: auto; }
.project-panel :deep(.el-tree-node__content) { height: 38px; }
.project-panel :deep(.el-tree-node.is-current > .el-tree-node__content) { background: #3478d4; color: #fff; }
.all-projects { width: 100%; margin: 12px 0 4px; padding: 10px; display: flex; justify-content: space-between; background: none; border: 0; border-radius: 4px; cursor: pointer; text-align: left; color: inherit; }
.all-projects.active { background: #3478d4; color: white; }
.project-content { display: flex; flex-direction: column; min-height: 650px; overflow: hidden; }
.project-content-heading { display: flex; align-items: center; justify-content: space-between; padding: 20px 22px 12px; }
.project-content-heading h2 { margin: 0 0 6px; font-size: 20px; }
.project-content-heading p { margin: 0; color: #8793a1; }
.project-toolbar { display: flex; align-items: center; gap: 10px; padding: 6px 20px 18px; flex-wrap: wrap; }
.project-toolbar > .el-input { width: 240px; }
.project-toolbar > .el-select { width: 130px; }
.project-toolbar-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-left: auto; }
.project-toolbar-actions :deep(.el-button + .el-button), .project-row-actions :deep(.el-button + .el-button) { margin-left: 0; }
.project-table-scroll { flex: 1; min-width: 0; overflow: auto; }
.project-table-scroll :deep(th.el-table__cell) { background: #f6f8fc; color: #78879b; }
.project-table-scroll :deep(.el-table .cell) { word-break: normal; }
.project-host-name, .project-spec { display: flex; flex-direction: column; align-items: flex-start; }
.project-host-name small, .project-spec span { max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.project-host-name small { color: #8793a1; font-size: 12px; }
.project-row-actions { display: flex; }
.project-row-actions .el-button { padding: 7px; }
.project-warning { color: #b7791f; }
.project-content-footer { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 14px; padding: 18px; border-top: 1px solid #e8edf5; color: #8793a1; font-size: 12px; }
.project-column-options { display: flex; flex-direction: column; }
.project-progress { padding: 8px 20px; }
.project-fullscreen { position: fixed; inset: 0; z-index: 1000; overflow: auto; padding: 24px; background: #f4f6f9; }
@media (max-width: 1080px) { .project-browser { grid-template-columns: 220px minmax(0, 1fr); } }
@media (max-width: 700px) { .project-browser { grid-template-columns: minmax(0, 1fr); } .project-panel { max-height: 260px; } .project-toolbar-actions { margin-left: 0; } .project-content-footer { overflow: auto; } }
</style>
