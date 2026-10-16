<template>
  <div class="page config-page">
    <div class="page-heading">
      <div><div class="eyebrow">资源管理</div><h1>文件管理</h1><p>配置远程主机和需要获取的文件路径。</p></div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增配置</el-button>
    </div>
    <div class="module-toolbar">
      <el-input v-model="search" :prefix-icon="Search" placeholder="搜索项目、主机或 IP" clearable @input="loadConfigs" />
      <span class="toolbar-count">共 {{ configs.length }} 个配置</span>
    </div>
    <div class="resource-list config-table">
      <div class="config-header file-config-grid"><span>项目</span><span>主机名称</span><span>IP 地址</span><span>机器名称</span><span>文件路径</span><span>状态</span><span>操作</span></div>
      <div v-for="item in configs" :key="item.id" class="config-row file-config-grid">
        <div class="primary-cell"><span class="table-avatar folder-avatar"><el-icon><FolderOpened /></el-icon></span><strong :title="item.project_path">{{ item.project_path }}</strong></div>
        <span>{{ item.host_name }}</span>
        <span>{{ item.ip_address }}:{{ item.port }}</span>
        <span>{{ item.machine_name }}</span>
        <span class="path-cell" :title="item.file_path">{{ item.file_path }}</span>
        <div class="file-config-status"><el-tag size="small" effect="plain" :type="item.fetch_status === 'success' ? 'primary' : item.fetch_status === 'error' ? 'danger' : 'info'" :title="fetchHint(item)">{{ fileCountText(item) }}</el-tag></div>
        <div class="file-config-actions">
          <el-tooltip content="编辑配置" placement="top"><el-button text :icon="EditPen" aria-label="编辑配置" :disabled="!!pendingActions[item.id] || saving" @click="openEdit(item)" /></el-tooltip>
          <el-tooltip content="获取文件列表" placement="top"><el-button text :icon="Refresh" aria-label="获取文件列表" :loading="!!pendingActions[item.id]" :disabled="!!pendingActions[item.id] || saving" @click="refreshFiles(item)" /></el-tooltip>
          <el-tooltip content="删除配置" placement="top"><el-button text type="danger" :icon="Delete" aria-label="删除配置" :disabled="!!pendingActions[item.id] || saving" @click="deleteConfig(item)" /></el-tooltip>
        </div>
      </div>
      <el-empty v-if="!configs.length" description="暂无文件管理配置" />
    </div>
  <el-dialog v-model="dialogVisible" :title="editing ? '编辑文件管理' : '新增文件管理'" width="520px" :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="beforeClose">
    <el-form ref="formRef" :model="form" :rules="rules" :disabled="saving || choicesLoading" label-position="top" @submit.prevent="save">
      <el-row :gutter="12">
        <el-col :span="12"><el-form-item label="项目" prop="project_id"><el-tree-select v-model="form.project_id" :data="projectTree(projects)" node-key="id" check-strictly filterable placeholder="选择项目" @change="projectChanged" /></el-form-item></el-col>
        <template v-if="!editing">
          <el-col :span="12"><el-form-item label="机器" prop="source_config_id"><el-select v-model="form.source_config_id" filterable clearable style="width:100%" :disabled="!form.project_id || !!choicesError" :loading="choicesLoading" :placeholder="form.project_id ? '选择项目下的机器' : '请先选择项目'" no-data-text="该项目暂无机器，请先在项目管理中新增"><el-option v-for="host in projectHosts" :key="host.id" :value="host.id" :label="machineLabel(host)" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="IP 地址"><el-input :model-value="selectedHost?.ip_address || ''" readonly /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="SSH 端口"><el-input :model-value="selectedHost ? String(selectedHost.port) : ''" readonly /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="关联账号"><el-input :model-value="selectedHost?.account_name || ''" readonly /></el-form-item></el-col>
        </template>
        <template v-else>
        <el-col :span="12"><el-form-item label="主机名称" prop="host_name"><el-input v-model="form.host_name" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="IP 地址" prop="ip_address"><el-input v-model="form.ip_address" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="SSH 端口"><el-input-number v-model="form.port" :min="1" :max="65535" controls-position="right" style="width:100%" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="关联账号" prop="account_id"><el-select v-model="form.account_id" style="width:100%" placeholder="选择账号"><el-option v-for="account in accounts" :key="account.id" :label="account.name" :value="account.id" /></el-select></el-form-item></el-col>
        </template>
      </el-row>
      <p class="muted-cell">{{ editing ? '账号保存后仅对当前配置生效。' : '机器信息来自项目管理，使用所选机器已保存的登录账号。' }}</p>
      <el-alert v-if="choicesError" :title="choicesError" type="error" :closable="false" />
      <el-form-item label="文件路径" prop="file_path"><el-input v-model="form.file_path" placeholder="例如：/etc/nginx/conf.d" /></el-form-item>
    </el-form>
    <template #footer><el-button :disabled="saving" @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="choicesLoading || (!editing && !!choicesError)" @click="save">保存</el-button></template>
  </el-dialog></div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, EditPen, FolderOpened, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { api } from '../api'
import { projectTree, type Project } from '../features/projects/model'
import { fileManagementConfigs, hostsForProject, machineLabel } from '../features/files/hostSelection'
type Config = { id: number; revision: number; updated_at: string; project: string; project_id: number; project_path: string; host_name: string; ip_address: string; machine_name: string; port: number; file_path: string; account_id: number; account_name: string; connection_status: string; connection_error: string; last_verified_at: string | null; fetch_status: string; fetch_error: string; file_count: number; last_fetched_at: string | null }
const pendingActions = reactive<Record<number, boolean>>({})
type Account = { id: number; name: string }
const configs = ref<Config[]>([]); const projects = ref<Project[]>([]); const accounts = ref<Account[]>([]); const search = ref(''); const dialogVisible = ref(false); const saving = ref(false); const editing = ref<Config | null>(null); const formRef = ref<FormInstance>()
const hostChoices = ref<Config[]>([]), choicesLoading = ref(false), choicesError = ref('')
const form = reactive({ project_id: undefined as number | undefined, source_config_id: undefined as number | undefined, host_name: '', ip_address: '', port: 22, file_path: '', account_id: undefined as number | undefined })
const projectHosts = computed(() => hostsForProject(hostChoices.value, form.project_id))
const selectedHost = computed(() => projectHosts.value.find(host => host.id === form.source_config_id))
const rules: FormRules = { project_id: [{ required: true, message: '请选择项目', trigger: 'change' }], host_name: [{ required: true, message: '请输入主机名称', trigger: 'blur' }], ip_address: [{ required: true, message: '请输入 IP 地址', trigger: 'blur' }], file_path: [{ required: true, message: '请输入文件路径', trigger: 'blur' }], account_id: [{ required: true, message: '请选择账号', trigger: 'change' }] }
rules.source_config_id = [{ required: true, message: '请选择机器', trigger: 'change' }]
let loadVersion = 0
async function loadConfigs() {
  const version = ++loadVersion
  try {
    const { data } = await api.get<Config[]>('/file-configs/', { params: { search: search.value } })
    if (version !== loadVersion) return
    configs.value = fileManagementConfigs(data.map(config => {
      const current = configs.value.find(item => item.id === config.id)
      return current && !isCurrentOrNewer(config, current) ? current : config
    }))
  } catch (error: any) { if (version === loadVersion) ElMessage.error(error.response?.data?.detail || '加载文件配置失败') }
}
async function loadAccounts() { const [a, p] = await Promise.all([api.get<Account[]>('/accounts/'), api.get<Project[]>('/projects/')]); accounts.value = a.data; projects.value = p.data }
let choicesVersion = 0
function projectChanged() { form.source_config_id = undefined; formRef.value?.clearValidate('source_config_id') }
async function openCreate() {
  if (saving.value) return
  const version = ++choicesVersion
  editing.value = null; choicesError.value = ''; hostChoices.value = []
  Object.assign(form, { project_id: undefined, source_config_id: undefined, host_name: '', ip_address: '', port: 22, file_path: '', account_id: undefined })
  dialogVisible.value = true; choicesLoading.value = true
  await nextTick(); formRef.value?.clearValidate()
  try {
    const [p, h] = await Promise.all([api.get<Project[]>('/projects/'), api.get<Config[]>('/file-configs/')])
    if (version !== choicesVersion) return
    projects.value = p.data; hostChoices.value = h.data
  } catch { if (version === choicesVersion) choicesError.value = '加载项目和机器失败，请关闭窗口后重试' }
  finally { if (version === choicesVersion) choicesLoading.value = false }
}
async function openEdit(item: Config) {
  if (saving.value) return
  choicesVersion++; choicesLoading.value = false; choicesError.value = ''
  editing.value = { ...item }
  Object.assign(form, { project_id: item.project_id, source_config_id: undefined, host_name: item.host_name, ip_address: item.ip_address, port: item.port, file_path: item.file_path, account_id: item.account_id })
  dialogVisible.value = true
  await nextTick(); formRef.value?.clearValidate()
}
async function save() {
  if (saving.value || choicesLoading.value || (!editing.value && choicesError.value)) return
  const target = editing.value ? { ...editing.value } : null
  const payload = { ...form, ...(target ? { revision: target.revision } : {}) }
  saving.value = true
  try {
    if (!await formRef.value?.validate().catch(() => false)) return
    if (target) {
      const response = await api.patch<Config>(`/file-configs/${target.id}/`, payload)
      applyConfig(response.data)
    } else {
      const host = selectedHost.value
      if (!host) { ElMessage.error('请选择当前项目下的机器'); return }
      await api.post('/file-configs/', {
        project_id: form.project_id, source_config_id: host.id,
        source_revision: host.revision, file_path: form.file_path,
      })
      await loadConfigs()
    }
    dialogVisible.value = false
    ElMessage.success('保存成功，仅更新当前配置')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}
function beforeClose(done: () => void) { if (!saving.value) done() }
async function refreshFiles(item: Config) {
  if (pendingActions[item.id]) return
  pendingActions[item.id] = true
  try {
    const response = await api.post<{ detail: string; config: Config }>(`/file-configs/${item.id}/refresh/`, undefined, { timeout: 120000 })
    applyConfig(response.data.config)
    ElMessage.success(response.data.detail)
  } catch (error: any) {
    if (error.response?.data?.config) applyConfig(error.response.data.config)
    else await loadConfigs()
    ElMessage.error(error.response?.data?.detail || (error.code === 'ECONNABORTED' ? '操作超时，请稍后刷新查看结果' : '远程操作失败'))
  } finally {
    delete pendingActions[item.id]
  }
}
function applyConfig(config: Config) {
  const current = configs.value.find(item => item.id === config.id)
  if (current && isCurrentOrNewer(config, current)) Object.assign(current, config)
}
function isCurrentOrNewer(incoming: Config, current: Config) {
  return incoming.revision > current.revision || (incoming.revision === current.revision && (incoming.updated_at ?? '') >= (current.updated_at ?? ''))
}
async function deleteConfig(item: Config) {
  try { await ElMessageBox.confirm(`删除“${item.host_name}”的配置？将同时删除本地文件列表缓存，不删除远程真实文件。`, '删除配置', { type: 'warning' }) }
  catch { return }
  try { await api.delete(`/file-configs/${item.id}/`, { data: { revision: item.revision } }); await loadConfigs(); ElMessage.success('删除成功') }
  catch (error: any) { ElMessage.error(error.response?.data?.detail || '删除失败') }
}
function fileCountText(item: Config) {
  return `文件：${item.file_count} 个`
}
function fetchHint(item: Config) {
  const fetched = item.last_fetched_at ? `上次获取：${new Date(item.last_fetched_at).toLocaleString('zh-CN')}，共 ${item.file_count} 个文件` : ''
  return [item.fetch_error, fetched, `递归统计 ${item.file_path} 下的全部文件，包含隐藏文件和隐藏目录内的文件，目录本身不计数`].filter(Boolean).join('\n')
}
onMounted(async () => { await Promise.all([loadConfigs(), loadAccounts()]) })
</script>
