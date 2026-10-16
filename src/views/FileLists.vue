<template>
  <div class="page file-browser-page">
    <div class="page-heading">
      <div><div class="eyebrow">资源管理</div><h1>文件列表</h1><p>按项目、主机和文件夹浏览已获取的文件，包含隐藏文件。</p></div>
      <el-button :icon="Refresh" :loading="loading" @click="loadFiles">刷新列表</el-button>
    </div>
    <div class="file-browser" v-loading="loading">
      <aside class="folder-panel">
        <div class="folder-panel-heading"><strong>目录列表</strong><span>{{ configs.length }} 个配置</span></div>
        <el-input v-model="treeSearch" :prefix-icon="Search" placeholder="搜索项目、主机或文件夹" clearable aria-label="搜索目录" />
        <div class="folder-tree-scroll">
          <el-tree ref="treeRef" :data="treeData" node-key="key" :current-node-key="activeKey" :default-expanded-keys="expandedKeys" :filter-node-method="filterNode" :expand-on-click-node="false" highlight-current :indent="18" empty-text="暂无配置" @node-click="selectNode">
            <template #default="{ data }"><span class="folder-tree-label" :title="data.title" :data-node-key="data.key"><el-icon><component :is="data.kind === 'host' ? Monitor : FolderOpened" /></el-icon><span>{{ data.label }}</span><small>{{ data.count }}</small></span></template>
          </el-tree>
        </div>
      </aside>
      <section class="folder-content">
        <div class="folder-content-heading"><div class="folder-location"><h2>{{ activeNode?.label || '选择文件夹' }}</h2><p :title="location">{{ location }}</p></div><el-tag effect="plain">{{ scopedFiles.length }} 个文件</el-tag></div>
        <div class="folder-file-toolbar">
          <el-input v-model="fileSearch" :prefix-icon="Search" placeholder="搜索当前范围内的文件" clearable aria-label="搜索文件" />
          <el-checkbox v-if="activeNode?.kind === 'folder'" v-model="recursive">包含子目录</el-checkbox>
          <span class="toolbar-count">显示 {{ visibleFiles.length }} 个文件</span>
        </div>
        <div v-if="activeConfig?.fetch_status === 'error'" class="folder-notice">最近一次获取失败：{{ activeConfig.fetch_error }}。当前展示上次成功获取的文件。</div>
        <div class="folder-table-scroll">
          <el-table :data="visibleFiles" class="folder-file-table" row-key="id" :empty-text="emptyText" style="width: 100%">
            <el-table-column label="文件名称" min-width="240" sortable prop="name"><template #default="{ row }"><div class="browser-file-name" title="双击编辑文件" @dblclick.stop="openEditor(row)"><span class="table-avatar file-avatar"><el-icon><Document /></el-icon></span><div><strong :title="row.name">{{ row.name }}</strong><small :title="row.relative_path">{{ row.relative_path }}</small></div></div></template></el-table-column>
            <el-table-column v-if="activeNode?.kind !== 'folder'" label="主机" min-width="140"><template #default="{ row }">{{ configById.get(row.file_config_id)?.host_name || '—' }}</template></el-table-column>
            <el-table-column label="文件大小" min-width="110" sortable prop="size"><template #default="{ row }">{{ formatSize(row.size) }}</template></el-table-column>
            <el-table-column label="修改时间" min-width="180" sortable prop="modified_at"><template #default="{ row }">{{ formatDate(row.modified_at) }}</template></el-table-column>
            <el-table-column label="获取状态" min-width="100"><template #default><el-tag size="small" effect="plain" type="success">已获取</el-tag></template></el-table-column>
            <el-table-column label="操作" width="100" fixed="right"><template #default="{ row }"><div class="admin-actions"><el-tooltip content="打开文件"><el-button text :icon="hasPermission('file_lists.edit') ? EditPen : View" :aria-label="hasPermission('file_lists.edit') ? '编辑文件' : '查看文件'" @click="openEditor(row)" /></el-tooltip><el-tooltip content="文件详情"><el-button text :icon="InfoFilled" aria-label="文件详情" @click="showDetail(row)" /></el-tooltip></div></template></el-table-column>
          </el-table>
        </div>
        <div class="folder-content-footer"><span>包含隐藏文件及隐藏目录内的文件，目录本身不计数</span><span v-if="activeConfig?.last_fetched_at">上次获取：{{ formatDate(activeConfig.last_fetched_at) }}</span></div>
      </section>
    </div>
    <el-dialog v-model="detailVisible" title="文件详情" width="560px">
      <el-descriptions v-if="selected" :column="1" border>
        <el-descriptions-item label="项目">{{ configById.get(selected.file_config_id)?.project_path }}</el-descriptions-item>
        <el-descriptions-item label="主机">{{ configById.get(selected.file_config_id)?.host_name }}（{{ configById.get(selected.file_config_id)?.ip_address }}）</el-descriptions-item>
        <el-descriptions-item label="文件名">{{ selected.name }}</el-descriptions-item>
        <el-descriptions-item label="完整路径"><span class="file-detail-path">{{ fullPath(selected) }}</span></el-descriptions-item>
        <el-descriptions-item label="大小">{{ formatSize(selected.size) }}</el-descriptions-item>
        <el-descriptions-item label="修改时间">{{ formatDate(selected.modified_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
    <el-dialog v-model="editorVisible" class="file-editor-dialog" width="86%" top="5vh" :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="beforeEditorClose" destroy-on-close>
      <template #header>
        <div class="file-editor-heading">
          <div><strong>{{ selected?.name || '文件编辑' }}</strong><small>{{ selected ? fullPath(selected) : '' }}</small></div>
          <el-tag size="small" effect="plain">{{ editorLanguage }}</el-tag>
        </div>
      </template>
      <div v-loading="editorLoading" class="file-editor-body">
        <CodeEditor v-if="selected && !editorLoading" v-model="editorContent" :filename="selected.name" :readonly="!hasPermission('file_lists.edit')" @language-change="editorLanguage = $event" @save="saveFile" />
      </div>
      <template #footer>
        <span class="editor-shortcut">{{ hasPermission('file_lists.edit') ? 'Ctrl / Cmd + S 保存' : '只读' }}</span>
        <el-button :disabled="saving" @click="cancelEditor">取消</el-button>
        <el-button v-if="hasPermission('file_lists.edit')" type="primary" :loading="saving" :disabled="editorLoading || !editorDirty" @click="saveFile">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type ElTree } from 'element-plus'
import { Document, EditPen, FolderOpened, InfoFilled, Monitor, Refresh, Search, View } from '@element-plus/icons-vue'
import { api } from '../api'
import { hasPermission } from '../composables/useAuth'
import { projectTree, type Project } from '../features/projects/model'

const CodeEditor = defineAsyncComponent(() => import('../components/CodeEditor.vue'))

type RemoteFile = { id: number; file_config_id: number; project: string; name: string; relative_path: string; file_type: string; size: number; modified_at: string | null }
type Config = { id: number; project: string; project_id: number; project_path: string; host_name: string; ip_address: string; port: number; file_path: string; directory_paths: string[]; fetch_status: string; fetch_error: string; last_fetched_at: string | null }
type FolderNode = { key: string; label: string; title: string; kind: 'project' | 'host' | 'folder'; configIds: number[]; path: string; count: number; children: FolderNode[] }
const files = ref<RemoteFile[]>([]), configs = ref<Config[]>([]), projects = ref<Project[]>([]), loading = ref(false)
const treeSearch = ref(''), fileSearch = ref(''), recursive = ref(false), activeKey = ref('')
const expandedKeys = ref<string[]>([]), treeRef = ref<InstanceType<typeof ElTree>>()
const detailVisible = ref(false), selected = ref<RemoteFile | null>(null)
const editorVisible = ref(false), editorLoading = ref(false), saving = ref(false)
const editorContent = ref(''), originalContent = ref(''), editorLanguage = ref('纯文本')
const editorDirty = computed(() => editorContent.value !== originalContent.value)
const configById = computed(() => new Map(configs.value.map(config => [config.id, config])))
const fileGroups = computed(() => {
  const groups = new Map<number, RemoteFile[]>()
  for (const file of files.value) {
    if (file.file_type === 'directory') continue
    if (!groups.has(file.file_config_id)) groups.set(file.file_config_id, [])
    groups.get(file.file_config_id)!.push(file)
  }
  return groups
})
const treeData = computed(() => {
  const projectNodes = projectTree(projects.value, configs.value)
  const projectMap = new Map<number, FolderNode>()
  const sourceById = new Map<number, ReturnType<typeof projectTree>[number]>()
  function indexSources(nodes: ReturnType<typeof projectTree>) {
    for (const node of nodes) { sourceById.set(node.id, node); indexSources(node.children) }
  }
  indexSources(projectNodes)
  function ensureProject(projectId: number): FolderNode {
    const existing = projectMap.get(projectId)
    if (existing) return existing
    const project = configs.value.find(config => config.project_id === projectId)
    const source = sourceById.get(projectId)
    const key = `project:${projectId}`
    const node: FolderNode = { key, label: source?.name || project?.project || '项目', title: source?.path || project?.project_path || '', kind: 'project', configIds: [], path: '', count: 0, children: [] }
    projectMap.set(projectId, node)
    for (const child of source?.children || []) {
      const childNode = ensureProject(child.id)
      node.children.push(childNode)
    }
    return node
  }
  for (const config of configs.value) {
    if (!config.file_path.trim()) continue
    const project = ensureProject(config.project_id)
    const hostKey = `${project.key}:host:${JSON.stringify([config.host_name, config.ip_address, config.port])}`
    let host = project.children.find(node => node.key === hostKey)
    if (!host) {
      host = { key: hostKey, label: `${config.host_name} · ${config.ip_address}`, title: `${config.host_name} · ${config.ip_address}:${config.port}`, kind: 'host', configIds: [], path: '', count: 0, children: [] }
      project.children.push(host)
    }
    const configFiles = fileGroups.value.get(config.id) || []
    project.configIds.push(config.id); host.configIds.push(config.id)
    project.count += configFiles.length; host.count += configFiles.length
    const root: FolderNode = { key: `config:${config.id}:`, label: config.file_path, title: config.file_path, kind: 'folder', configIds: [config.id], path: '', count: configFiles.length, children: [] }
    host.children.push(root)
    const folders = new Map<string, FolderNode>([['', root]])
    function ensureFolder(path: string): FolderNode {
      const existing = folders.get(path)
      if (existing) return existing
      const parts = path.split('/'), label = parts.pop()!
      const parent = ensureFolder(parts.join('/'))
      const node: FolderNode = { key: `config:${config.id}:${path}`, label, title: `${config.file_path.replace(/\/+$/, '')}/${path}`, kind: 'folder', configIds: [config.id], path, count: 0, children: [] }
      parent.children.push(node); folders.set(path, node)
      return node
    }
    for (const path of config.directory_paths || []) if (path && !path.startsWith('/')) ensureFolder(path)
    for (const file of configFiles) {
      if (file.relative_path.startsWith('/')) continue
      const parts = file.relative_path.split('/'); parts.pop()
      if (parts.length) ensureFolder(parts.join('/'))
      while (parts.length) { folders.get(parts.join('/'))!.count++; parts.pop() }
    }
    for (const folder of folders.values()) folder.children.sort((a, b) => a.label.localeCompare(b.label, 'zh-CN'))
  }
  const roots = projectNodes.map(p => ensureProject(p.id))
  function collect(node: FolderNode) {
    for (const child of node.children) if (child.kind === 'project') {
      collect(child)
      node.configIds.push(...child.configIds)
      node.count += child.count
    }
  }
  for (const root of roots) collect(root)
  return roots
})
const nodeMap = computed(() => {
  const nodes = new Map<string, FolderNode>()
  function visit(items: FolderNode[]) { for (const item of items) { nodes.set(item.key, item); visit(item.children) } }
  visit(treeData.value)
  return nodes
})
const activeNode = computed(() => nodeMap.value.get(activeKey.value))
const activeConfig = computed(() => activeNode.value?.configIds.length === 1 ? configById.value.get(activeNode.value.configIds[0]!) : undefined)
const location = computed(() => {
  const node = activeNode.value, config = activeConfig.value
  if (!node) return '从左侧选择项目、主机或文件夹'
  if (node.kind === 'folder' && config) return `${config.project_path} / ${config.host_name} (${config.ip_address}:${config.port}) · ${node.title}`
  return node.kind === 'project' ? `${node.label} · 所有主机的文件` : `${node.title} · 所有配置目录的文件`
})
const scopedFiles = computed(() => {
  const node = activeNode.value
  if (!node) return []
  const candidates = node.configIds.flatMap(id => fileGroups.value.get(id) || [])
  if (node.kind !== 'folder') return candidates
  return candidates.filter(file => {
    if (file.relative_path.startsWith('/')) return !node.path
    const parent = file.relative_path.split('/').slice(0, -1).join('/')
    return parent === node.path || (recursive.value && (!node.path || parent.startsWith(node.path + '/')))
  })
})
const visibleFiles = computed(() => {
  const query = fileSearch.value.trim().toLocaleLowerCase()
  return scopedFiles.value.filter(file => !query || `${file.name} ${file.relative_path}`.toLocaleLowerCase().includes(query))
})
const emptyText = computed(() => {
  if (!activeNode.value) return '请先从左侧选择文件夹'
  if (fileSearch.value) return '没有匹配的文件'
  if (activeConfig.value?.fetch_status === 'pending') return '尚未获取文件，请先在文件管理中获取文件列表'
  return activeNode.value.kind === 'folder' && !recursive.value ? '此文件夹没有直属文件，可选择子目录或勾选“包含子目录”' : '此范围内暂无文件'
})
function filterNode(value: string, data: FolderNode): boolean { const query = value.trim().toLocaleLowerCase(); return !query || `${data.label} ${data.title}`.toLocaleLowerCase().includes(query) }
watch(treeSearch, value => treeRef.value?.filter(value))
function selectNode(node: FolderNode) { activeKey.value = node.key; fileSearch.value = '' }
async function loadFiles() {
  if (loading.value) return
  loading.value = true
  try {
    const [fileResponse, configResponse, projectResponse] = await Promise.all([api.get<RemoteFile[]>('/file-lists/'), api.get<Config[]>('/file-configs/'), api.get<Project[]>('/projects/')])
    files.value = fileResponse.data; configs.value = configResponse.data; projects.value = projectResponse.data
    if (!nodeMap.value.has(activeKey.value)) activeKey.value = configs.value[0] ? `config:${configs.value[0].id}:` : ''
    if (!expandedKeys.value.length) {
      const keys: string[] = []
      function expand(nodes: FolderNode[]) { for (const node of nodes) { keys.push(node.key); expand(node.children) } }
      expand(treeData.value)
      expandedKeys.value = keys
    }
    await nextTick()
    treeRef.value?.setCurrentKey(activeKey.value); treeRef.value?.filter(treeSearch.value)
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '加载文件列表失败') }
  finally { loading.value = false }
}
function showDetail(item: RemoteFile) { selected.value = item; detailVisible.value = true }
async function openEditor(item: RemoteFile) {
  if (editorLoading.value || saving.value) return
  selected.value = item
  editorContent.value = ''
  originalContent.value = ''
  editorLanguage.value = '识别中'
  editorVisible.value = true
  editorLoading.value = true
  try {
    const response = await api.get<{ file: RemoteFile; content: string; encoding: string }>(`/file-lists/${item.id}/`, { timeout: 30000 })
    if (selected.value?.id !== item.id || !editorVisible.value) return
    Object.assign(item, response.data.file)
    editorContent.value = response.data.content
    originalContent.value = response.data.content
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '读取文件失败')
    editorVisible.value = false
  } finally { editorLoading.value = false }
}
async function saveFile() {
  if (!hasPermission('file_lists.edit') || !selected.value || editorLoading.value || saving.value || !editorDirty.value) return
  saving.value = true
  try {
    const response = await api.patch<{ detail: string; file: RemoteFile }>(`/file-lists/${selected.value.id}/`, { content: editorContent.value }, { timeout: 30000 })
    const current = files.value.find(file => file.id === selected.value?.id)
    if (current) Object.assign(current, response.data.file)
    Object.assign(selected.value, response.data.file)
    originalContent.value = editorContent.value
    ElMessage.success(response.data.detail || '文件保存成功')
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '保存文件失败') }
  finally { saving.value = false }
}
async function canCloseEditor() {
  if (!editorDirty.value) return true
  try {
    await ElMessageBox.confirm('文件有未保存的修改，确定放弃吗？', '放弃修改', { confirmButtonText: '放弃', cancelButtonText: '继续编辑', type: 'warning' })
    return true
  } catch { return false }
}
async function cancelEditor() { if (await canCloseEditor()) editorVisible.value = false }
async function beforeEditorClose(done: () => void) { if (!saving.value && await canCloseEditor()) done() }
function fullPath(file: RemoteFile) { return file.relative_path.startsWith('/') ? file.relative_path : `${configById.value.get(file.file_config_id)?.file_path.replace(/\/+$/, '') || ''}/${file.relative_path}` }
function formatSize(size: number) { if (size < 1024) return `${size} B`; if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`; return `${(size / 1024 / 1024).toFixed(1)} MB` }
function formatDate(value: string | null) { return value ? new Date(value).toLocaleString('zh-CN') : '—' }
onMounted(loadFiles)
</script>

<style scoped>
.file-browser { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 16px; align-items: stretch; }
.folder-panel, .folder-content { min-width: 0; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; }
.folder-panel { padding: 18px 12px; }
.folder-panel-heading { display: flex; justify-content: space-between; align-items: center; padding: 0 4px 16px; }
.folder-panel-heading strong { font-size: 16px; }
.folder-panel-heading > span { font-size: 12px; color: #8793a1; }
.folder-panel > .el-input { margin-bottom: 16px; }
.folder-tree-scroll { max-height: calc(100vh - 310px); min-height: 420px; overflow: auto; }
.folder-tree-scroll :deep(.el-tree) { min-width: max-content; background: transparent; font-size: 14px; }
.folder-tree-scroll :deep(.el-tree-node__content) { height: 39px; border-radius: 5px; padding-right: 10px; }
.folder-tree-scroll :deep(.el-tree-node.is-current > .el-tree-node__content) { background: #3478d4; color: white; }
.folder-tree-scroll :deep(.el-tree-node.is-current > .el-tree-node__content small), .folder-tree-scroll :deep(.el-tree-node.is-current > .el-tree-node__content .el-tree-node__expand-icon) { color: white; }
.folder-tree-label { display: flex; flex: 1; align-items: center; gap: 7px; padding-right: 4px; }
.folder-tree-label > .el-icon { flex-shrink: 0; }
.folder-tree-label > span { max-width: 310px; overflow: hidden; text-overflow: ellipsis; }
.folder-tree-label small { margin-left: auto; padding-left: 14px; font-size: 12px; color: #94a0b0; }
.folder-content { overflow: hidden; display: flex; flex-direction: column; min-height: 580px; }
.folder-content-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 20px 22px 16px; }
.folder-location { min-width: 0; }
.folder-location h2 { margin: 0 0 7px; font-size: 18px; overflow-wrap: anywhere; }
.folder-location p { margin: 0; color: #8793a1; font-size: 12px; overflow-wrap: anywhere; }
.folder-content-heading > .el-tag { flex-shrink: 0; }
.folder-file-toolbar { display: flex; align-items: center; gap: 16px; padding: 0 22px 17px; flex-wrap: wrap; }
.folder-file-toolbar > .el-input { width: 270px; max-width: 100%; }
.folder-file-toolbar :deep(.el-checkbox__label) { font-size: 13px; }
.folder-table-scroll { flex: 1; min-width: 0; }
.folder-file-table { --el-table-header-bg-color: #f7f9fd; --el-table-header-text-color: #768396; font-size: 13px; }
.folder-file-table :deep(th.el-table__cell) { height: 45px; font-weight: 500; }
.folder-file-table :deep(td.el-table__cell) { height: 70px; }
.folder-file-table :deep(.cell) { padding-left: 18px; padding-right: 14px; }
.browser-file-name { display: flex; align-items: center; gap: 10px; min-width: 0; }
.browser-file-name { cursor: pointer; }
.browser-file-name > div { min-width: 0; }
.browser-file-name strong, .browser-file-name small { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.browser-file-name strong { color: #38475a; font-weight: 600; font-size: 13px; }
.browser-file-name small { margin-top: 3px; color: #98a2b1; font-size: 12px; }
.folder-content-footer { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; padding: 14px 22px; border-top: 1px solid #edf0f4; color: #939ca9; font-size: 12px; }
.folder-notice { padding: 10px 22px; color: #b88230; background: #fdf6ec; font-size: 12px; }
.file-detail-path { overflow-wrap: anywhere; }
.file-editor-heading { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding-right: 28px; }
.file-editor-heading > div { min-width: 0; }
.file-editor-heading strong, .file-editor-heading small { display: block; }
.file-editor-heading strong { color: #24364d; font-size: 16px; }
.file-editor-heading small { margin-top: 5px; color: #8995a5; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-editor-body { min-height: 420px; }
.file-editor-dialog :deep(.el-dialog__body) { padding: 8px 20px 12px; }
.file-editor-dialog :deep(.el-dialog__footer) { display: flex; align-items: center; justify-content: flex-end; gap: 10px; }
.editor-shortcut { margin-right: auto; color: #8b96a6; font-size: 12px; }
@media (max-width: 1100px) { .file-browser { grid-template-columns: 240px minmax(0, 1fr); gap: 12px; } }
@media (max-width: 760px) { .file-browser { grid-template-columns: minmax(0, 1fr); } .folder-tree-scroll { min-height: 100px; max-height: 260px; } .folder-content { min-height: 420px; } }
</style>
