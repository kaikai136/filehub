<template>
  <div class="page config-page"><div class="page-heading"><div><div class="eyebrow">资源管理</div><h1>文件管理</h1><p>配置远程主机和需要获取的文件路径。</p></div><el-button type="primary" :icon="Plus" @click="openCreate">新增配置</el-button></div><div class="module-toolbar"><el-input v-model="search" :prefix-icon="Search" placeholder="搜索项目、主机或 IP" clearable @input="loadConfigs" /><span class="toolbar-count">共 {{ configs.length }} 个配置</span></div><div class="resource-list config-table"><div class="config-header file-config-grid"><span>项目</span><span>主机名称</span><span>IP 地址</span><span>机器名称</span><span>文件路径</span><span>状态</span><span>操作</span></div><div v-for="item in configs" :key="item.id" class="config-row file-config-grid"><div class="primary-cell"><span class="table-avatar folder-avatar"><el-icon><FolderOpened /></el-icon></span><strong>{{ item.project }}</strong></div><span>{{ item.host_name }}</span><span>{{ item.ip_address }}:{{ item.port }}</span><span>{{ item.machine_name }}</span><span class="path-cell" :title="item.file_path">{{ item.file_path }}</span><div class="file-config-status">
  <el-tag size="small" effect="plain" :type="pendingActions[item.id] ? 'primary' : statusType(item.connection_status)" :title="connectionHint(item)">
    {{ pendingActions[item.id] ? '验证中…' : connectionText(item.connection_status) }}
  </el-tag>
  <el-tag size="small" effect="plain" :type="pendingActions[item.id] === 'refresh' ? 'primary' : item.fetch_status === 'success' ? 'primary' : statusType(item.fetch_status)" :title="fetchHint(item)">
    {{ pendingActions[item.id] === 'refresh' ? '获取中…' : fileCountText(item) }}
  </el-tag>
</div><el-dropdown @command="(command: string | number | object) => handleCommand(String(command), item)"><el-button text :icon="MoreFilled" :loading="!!pendingActions[item.id]" :disabled="!!pendingActions[item.id] || saving" /><template #dropdown><el-dropdown-menu><el-dropdown-item command="edit">编辑</el-dropdown-item><el-dropdown-item command="test">测试连接</el-dropdown-item><el-dropdown-item command="refresh">获取文件列表</el-dropdown-item><el-dropdown-item command="delete" divided>删除</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div><el-empty v-if="!configs.length" description="暂无文件管理配置" /></div>
  <el-dialog v-model="dialogVisible" :title="editing ? '编辑文件管理' : '新增文件管理'" width="520px" :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="beforeClose">
    <el-form ref="formRef" :model="form" :rules="rules" :disabled="saving" label-position="top" @submit.prevent="save">
      <el-row :gutter="12">
        <el-col :span="12"><el-form-item label="项目" prop="project"><el-input v-model="form.project" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="主机名称" prop="host_name"><el-input v-model="form.host_name" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="IP 地址" prop="ip_address"><el-input v-model="form.ip_address" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="机器名称" prop="machine_name"><el-input v-model="form.machine_name" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="SSH 端口"><el-input-number v-model="form.port" :min="1" :max="65535" controls-position="right" style="width:100%" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="关联账号" prop="account_id"><el-select v-model="form.account_id" style="width:100%" placeholder="选择账号"><el-option v-for="account in accounts" :key="account.id" :label="account.name" :value="account.id" /></el-select></el-form-item></el-col>
      </el-row>
      <p class="muted-cell">账号保存后仅对当前机器生效，其他机器的登录信息保持独立。</p>
      <el-form-item label="文件路径" prop="file_path"><el-input v-model="form.file_path" placeholder="例如：/etc/nginx/conf.d" /></el-form-item>
    </el-form>
    <template #footer><el-button :disabled="saving" @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </el-dialog></div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { FolderOpened, MoreFilled, Plus, Search } from '@element-plus/icons-vue'
import { api } from '../api'
type Config = { id: number; revision: number; updated_at: string; project: string; host_name: string; ip_address: string; machine_name: string; port: number; file_path: string; account_id: number; account_name: string; connection_status: string; connection_error: string; last_verified_at: string | null; fetch_status: string; fetch_error: string; file_count: number; last_fetched_at: string | null }
const pendingActions = reactive<Record<number, 'test-connection' | 'refresh'>>({})
type Account = { id: number; name: string }
const configs = ref<Config[]>([]); const accounts = ref<Account[]>([]); const search = ref(''); const dialogVisible = ref(false); const saving = ref(false); const editing = ref<Config | null>(null); const formRef = ref<FormInstance>()
const form = reactive({ project: '', host_name: '', ip_address: '', machine_name: '', port: 22, file_path: '', account_id: undefined as number | undefined })
const rules: FormRules = { project: [{ required: true, message: '请输入项目', trigger: 'blur' }], host_name: [{ required: true, message: '请输入主机名称', trigger: 'blur' }], ip_address: [{ required: true, message: '请输入 IP 地址', trigger: 'blur' }], machine_name: [{ required: true, message: '请输入机器名称', trigger: 'blur' }], file_path: [{ required: true, message: '请输入文件路径', trigger: 'blur' }], account_id: [{ required: true, message: '请选择账号', trigger: 'change' }] }
let loadVersion = 0
async function loadConfigs() {
  const version = ++loadVersion
  try {
    const { data } = await api.get<Config[]>('/file-configs/', { params: { search: search.value } })
    if (version !== loadVersion) return
    configs.value = data.map(config => {
      const current = configs.value.find(item => item.id === config.id)
      return current && !isCurrentOrNewer(config, current) ? current : config
    })
  } catch (error: any) { if (version === loadVersion) ElMessage.error(error.response?.data?.detail || '加载文件配置失败') }
}
async function loadAccounts() { accounts.value = (await api.get<Account[]>('/accounts/')).data }
function openCreate() { if (saving.value) return; editing.value = null; Object.assign(form, { project: '', host_name: '', ip_address: '', machine_name: '', port: 22, file_path: '', account_id: undefined }); dialogVisible.value = true }
function openEdit(item: Config) { if (saving.value) return; editing.value = { ...item }; Object.assign(form, { project: item.project, host_name: item.host_name, ip_address: item.ip_address, machine_name: item.machine_name, port: item.port, file_path: item.file_path, account_id: item.account_id }); dialogVisible.value = true }
async function save() {
  if (saving.value) return
  const target = editing.value ? { ...editing.value } : null
  const payload = { ...form, ...(target ? { revision: target.revision } : {}) }
  saving.value = true
  try {
    if (!await formRef.value?.validate().catch(() => false)) return
    if (target) {
      const response = await api.patch<Config>(`/file-configs/${target.id}/`, payload)
      applyConfig(response.data)
    } else {
      await api.post('/file-configs/', payload)
      await loadConfigs()
    }
    dialogVisible.value = false
    ElMessage.success('保存成功，仅更新当前配置')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}
function beforeClose(done: () => void) { if (!saving.value) done() }
async function action(item: Config, type: 'test-connection' | 'refresh') {
  if (pendingActions[item.id]) return
  pendingActions[item.id] = type
  try {
    const response = await api.post<{ detail: string; config: Config }>(`/file-configs/${item.id}/${type}/`, undefined, { timeout: 120000 })
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
async function handleCommand(command: string, item: Config) { if (command === 'edit') return openEdit(item); if (command === 'test') return action(item, 'test-connection'); if (command === 'refresh') return action(item, 'refresh'); if (command === 'delete') await ElMessageBox.confirm(`确定删除项目“${item.project}”吗？`, '删除配置', { type: 'warning' }).then(async () => { await api.delete(`/file-configs/${item.id}/`); await loadConfigs(); ElMessage.success('删除成功') }).catch(() => undefined) }
function connectionText(status: string) { return status === 'success' ? '已验证' : status === 'error' ? '验证失败' : '未验证' }
function fileCountText(item: Config) {
  if (item.fetch_status === 'success') return `文件：${item.file_count} 个`
  if (item.fetch_status === 'error') return item.last_fetched_at ? `文件：${item.file_count} 个 · 获取失败` : '获取失败'
  return '未获取文件'
}
function connectionHint(item: Config) {
  if (pendingActions[item.id]) return '正在验证 SSH 登录'
  if (item.connection_status === 'error') return item.connection_error
  return item.last_verified_at ? `SSH 登录已验证：${new Date(item.last_verified_at).toLocaleString('zh-CN')}` : '尚未验证 SSH 登录'
}
function fetchHint(item: Config) {
  const fetched = item.last_fetched_at ? `上次获取：${new Date(item.last_fetched_at).toLocaleString('zh-CN')}，共 ${item.file_count} 个文件` : ''
  return [item.fetch_error, fetched, `递归统计 ${item.file_path} 下的全部文件，包含隐藏文件和隐藏目录内的文件，目录本身不计数`].filter(Boolean).join('\n')
}
function statusType(status: string) { return status === 'success' ? 'success' : status === 'error' ? 'danger' : 'info' }
onMounted(async () => { await Promise.all([loadConfigs(), loadAccounts()]) })
</script>
