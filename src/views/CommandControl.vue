<template>
  <div class="page command-control-page">
    <div class="page-heading">
      <div><div class="eyebrow">系统管理</div><h1>命令控制</h1><p>配置 Shell 危险命令黑名单，保存后对新提交和待执行任务生效。</p></div>
      <el-button v-if="canEdit" type="primary" :icon="Check" class="icon-success" :loading="saving" :disabled="loading || !!loadError" @click="save">保存规则</el-button>
    </div>
    <el-alert title="仅限制 Shell，K8s 不受此黑名单约束。黑名单不能保证拦截所有危险操作，请配合远程最小权限账户使用。" type="warning" :closable="false" show-icon />
    <el-alert class="policy-notice" title="重定向、变量替换、后台执行、流程控制和动态命令等语法限制始终生效，不随命令规则启停。仅超级管理员可以修改规则。" type="info" :closable="false" show-icon />
    <el-alert v-if="errorMessage" class="policy-notice" :title="errorMessage" type="error" :closable="false" show-icon />
    <div class="policy-toolbar">
      <el-input v-model="search" :prefix-icon="Search" class="icon-primary" clearable placeholder="搜索命令或分类" aria-label="搜索命令或分类" />
      <span>{{ rules.length }} 条规则 · {{ rules.filter(rule => rule.enabled).length }} 条启用</span>
      <el-button :icon="Refresh" class="icon-primary" :loading="loading" :disabled="saving" @click="reload">刷新</el-button>
      <template v-if="canEdit">
        <el-button :icon="Plus" class="icon-success" :disabled="loading || saving || !!loadError" @click="addRule">新增规则</el-button>
        <el-button :disabled="loading || saving || !!loadError" @click="restoreDefaults">恢复内置规则</el-button>
      </template>
    </div>
    <el-table :data="filteredRules" class="admin-table" v-loading="loading" empty-text="暂无匹配的命令规则">
      <el-table-column label="命令名称" min-width="210"><template #default="{ row }"><el-input v-if="canEdit" v-model="row.command" maxlength="80" :disabled="saving" aria-label="命令名称" /><code v-else>{{ row.command }}</code></template></el-table-column>
      <el-table-column label="分类 / 拦截原因" min-width="190"><template #default="{ row }"><el-input v-if="canEdit" v-model="row.category" maxlength="80" :disabled="saving" aria-label="规则分类" /><span v-else>{{ row.category }}</span></template></el-table-column>
      <el-table-column label="匹配方式" min-width="190"><template #default="{ row }"><el-select v-if="canEdit" v-model="row.match" :disabled="saving" aria-label="匹配方式"><el-option label="精确名称" value="exact" /><el-option label="名称前缀" value="prefix" /><el-option label="Python 数字版本" value="python_version" /></el-select><span v-else>{{ matchLabels[row.match] }}</span></template></el-table-column>
      <el-table-column label="启用" width="100"><template #default="{ row }"><el-switch v-model="row.enabled" :disabled="!canEdit || saving" aria-label="启用规则" /></template></el-table-column>
    </el-table>
    <p class="policy-help">命令只填写名称，不填写参数或路径；绝对路径命令按文件名匹配。前缀示例：mkfs. 匹配 mkfs.ext4；Python 数字版本匹配 python、python3、python3.13。规则可停用，不提供删除；停用所有规则会削弱保护。</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { api } from '../api'

type CommandRule = { command: string; category: string; match: 'exact' | 'prefix' | 'python_version'; enabled: boolean }
type CommandPolicy = { rules: CommandRule[]; defaults: CommandRule[]; revision: number; updated_at: string; can_edit: boolean }
const rules = ref<CommandRule[]>([]), defaults = ref<CommandRule[]>([])
const revision = ref(0), canEdit = ref(false), loading = ref(true), saving = ref(false)
const search = ref(''), errorMessage = ref(''), loadError = ref('')
const matchLabels = { exact: '精确名称', prefix: '名称前缀', python_version: 'Python 数字版本' }
const filteredRules = computed(() => rules.value.filter(rule => (rule.command + ' ' + rule.category).toLowerCase().includes(search.value.toLowerCase())))
let savedRules = ''
function applyPolicy(data: CommandPolicy) {
  rules.value = data.rules
  defaults.value = data.defaults
  revision.value = data.revision
  canEdit.value = data.can_edit
  savedRules = JSON.stringify(data.rules)
}
async function load() {
  loading.value = true
  errorMessage.value = ''
  try { const { data } = await api.get<CommandPolicy>('/command-control/'); applyPolicy(data); loadError.value = '' }
  catch (error: any) { loadError.value = error.response?.data?.detail || '加载命令控制失败'; errorMessage.value = loadError.value }
  finally { loading.value = false }
}
async function reload() {
  if (JSON.stringify(rules.value) !== savedRules && savedRules) {
    try { await ElMessageBox.confirm('刷新将丢弃未保存修改，是否继续？', '刷新规则', { type: 'warning' }) } catch { return }
  }
  await load()
}
function addRule() { search.value = ''; rules.value.unshift({ command: '', category: '自定义', match: 'exact', enabled: true }) }
async function restoreDefaults() {
  try { await ElMessageBox.confirm('恢复将替换当前全部规则，保存后生效。是否继续？', '恢复内置规则', { type: 'warning' }) } catch { return }
  rules.value = defaults.value.map(rule => ({ ...rule }))
  search.value = ''
}
async function save() {
  if (saving.value) return
  errorMessage.value = ''
  saving.value = true
  try {
    const { data } = await api.patch<CommandPolicy>('/command-control/', { rules: rules.value, revision: revision.value })
    applyPolicy(data)
    ElMessage.success('命令规则已保存')
  } catch (error: any) { errorMessage.value = error.response?.data?.detail || '保存命令规则失败'; ElMessage.error(errorMessage.value) }
  finally { saving.value = false }
}
onMounted(load)
</script>

<style scoped>
.policy-notice { margin-top: 12px; }
.policy-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin: 18px 0; }
.policy-toolbar .el-input { max-width: 290px; }
.policy-toolbar > span, .policy-help { color: #737d8c; font-size: 13px; }
.policy-help { line-height: 1.8; }
</style>
