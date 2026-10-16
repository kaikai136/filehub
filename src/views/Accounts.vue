<template>
  <div class="page config-page">
    <div class="page-heading"><div><div class="eyebrow">资源管理</div><h1>账号管理</h1><p>维护 SSH 账号；修改后，在对应机器中选择账号并保存生效，各机器独立更新。</p></div><el-button v-if="hasPermission('accounts.create')" type="primary" :icon="Plus" @click="openCreate">新增账号</el-button></div>
    <div class="module-toolbar"><el-input v-model="search" :prefix-icon="Search" placeholder="搜索账号名称或用户" clearable @input="loadAccounts" /><span class="toolbar-count">共 {{ accounts.length }} 个账号</span></div>
    <div class="resource-list config-table">
      <div class="config-header account-grid"><span>账号名称</span><span>用户</span><span>密码</span><span>独立密钥</span><span>备注</span><span>状态</span><span>操作</span></div>
      <div v-for="item in accounts" :key="item.id" class="config-row account-grid">
        <div class="primary-cell"><span class="table-avatar"><el-icon><Key /></el-icon></span><strong>{{ item.name }}</strong></div>
        <span>{{ item.username }}</span>
        <span class="secret-cell">{{ item.has_password ? '已配置' : '未配置' }}</span>
        <span class="secret-cell">{{ item.has_private_key ? 'id_rsa' : '未配置' }}</span>
        <span class="muted-cell">{{ item.note || '无备注' }}</span>
        <el-tag class="account-status" effect="plain" :type="item.is_active ? 'success' : 'info'">{{ item.is_active ? '启用' : '禁用' }}</el-tag>
        <div class="account-actions">
          <el-tooltip v-if="hasPermission('accounts.edit')" content="编辑账号" placement="top"><el-button text :icon="EditPen" aria-label="编辑账号" :disabled="saving" @click="handleCommand('edit', item)" /></el-tooltip>
          <el-tooltip v-if="hasPermission('accounts.edit')" :content="item.is_active ? '禁用账号' : '启用账号'" placement="top"><el-button text :icon="item.is_active ? VideoPause : VideoPlay" :aria-label="item.is_active ? '禁用账号' : '启用账号'" :disabled="saving" @click="handleCommand('toggle', item)" /></el-tooltip>
          <el-tooltip v-if="hasPermission('accounts.delete')" content="删除账号" placement="top"><el-button text type="danger" :icon="Delete" aria-label="删除账号" :disabled="saving" @click="handleCommand('delete', item)" /></el-tooltip>
        </div>
      </div>
      <el-empty v-if="!accounts.length" description="暂无账号" />
    </div>
    <el-dialog
      v-model="dialogVisible"
      class="account-dialog"
      modal-class="account-dialog-overlay"
      :title="editing ? '编辑账号' : '新增账号'"
      width="680px"
      align-center
      :close-on-click-modal="false"
      :close-on-press-escape="!saving"
      :before-close="beforeClose"
      @closed="resetForm"
    >
      <el-form ref="formRef" class="account-form" :model="form" :rules="rules" :disabled="saving" label-position="left" label-width="92px" @submit.prevent="save">
        <div class="account-form-grid">
          <el-form-item label="账号名称" prop="name">
            <el-input v-model="form.name" autocomplete="off" />
          </el-form-item>
          <el-form-item label="用户" prop="username">
            <el-input v-model="form.username" autocomplete="off" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" show-password autocomplete="new-password" :placeholder="editing ? '留空保留原密码' : ''" />
          </el-form-item>
          <el-form-item label="独立密钥" class="account-key-field">
            <div class="account-key-upload">
              <input ref="keyInput" type="file" hidden aria-label="选择独立密钥文件" @change="selectPrivateKey" />
              <el-button :disabled="saving || readingKey" :loading="readingKey" @click="keyInput?.click()">{{ keyFileName ? '重新上传' : '点击上传' }}</el-button>
              <span class="account-key-status" :class="{ 'is-selected': keyFileName }" :title="keyFileName || undefined" aria-live="polite">{{ keyFileName || (editing?.has_private_key ? '已配置独立密钥' : '未上传独立密钥') }}</span>
            </div>
          </el-form-item>
          <el-form-item class="account-note-field" label="备注信息">
            <el-input v-model="form.note" type="textarea" :rows="4" resize="vertical" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="readingKey" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, EditPen, Key, Plus, Search, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import { api } from '../api'
import { hasPermission } from '../composables/useAuth'
type Account = { id: number; name: string; username: string; note: string; is_active: boolean; has_password: boolean; has_private_key: boolean }
const accounts = ref<Account[]>([]); const search = ref(''); const dialogVisible = ref(false); const saving = ref(false); const editing = ref<Account | null>(null); const formRef = ref<FormInstance>()
const form = reactive({ name: '', username: '', password: '', private_key: '', note: '', is_active: true })
const keyInput = ref<HTMLInputElement>()
const keyFileName = ref('')
const readingKey = ref(false)
let keyReadVersion = 0
const rules: FormRules = { name: [{ required: true, whitespace: true, message: '请输入账号名称', trigger: 'blur' }], username: [{ required: true, whitespace: true, message: '请输入用户', trigger: 'blur' }] }
async function loadAccounts() { try { accounts.value = (await api.get<Account[]>('/accounts/', { params: { search: search.value } })).data } catch (error: any) { ElMessage.error(error.response?.data?.detail || '加载账号失败') } }
function resetForm() {
  keyReadVersion++
  readingKey.value = false
  keyFileName.value = ''
  if (keyInput.value) keyInput.value.value = ''
  editing.value = null
  Object.assign(form, { name: '', username: '', password: '', private_key: '', note: '', is_active: true })
  formRef.value?.clearValidate()
}
function openCreate() {
  resetForm()
  dialogVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}
function openEdit(item: Account) {
  resetForm()
  editing.value = { ...item }
  Object.assign(form, { name: item.name, username: item.username, note: item.note, is_active: item.is_active })
  dialogVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}
function beforeClose(done: () => void) {
  if (!saving.value) done()
}
async function selectPrivateKey(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > 1024 * 1024) {
    ElMessage.error('密钥文件不能超过 1 MB')
    return
  }
  const version = ++keyReadVersion
  readingKey.value = true
  try {
    const content = await file.text()
    if (version !== keyReadVersion || !dialogVisible.value) return
    if (!content.trim() || content.includes('\u0000')) {
      ElMessage.error('请选择包含 SSH 私钥的文本文件')
      return
    }
    form.private_key = content
    keyFileName.value = file.name
  } catch {
    if (version === keyReadVersion) ElMessage.error('密钥文件读取失败，请重新上传')
  } finally {
    if (version === keyReadVersion) readingKey.value = false
  }
}
async function save() {
  if (saving.value || readingKey.value) return
  const targetId = editing.value?.id
  const payload = { ...form, name: form.name.trim(), username: form.username.trim() }
  saving.value = true
  try {
    if (!await formRef.value?.validate().catch(() => false)) return
    if (targetId !== undefined) await api.patch(`/accounts/${targetId}/`, payload)
    else await api.post('/accounts/', payload)
    dialogVisible.value = false
    ElMessage.success('保存成功')
    await loadAccounts()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
async function handleCommand(command: string, item: Account) { if (command === 'edit') return openEdit(item); if (command === 'toggle') { try { await api.patch(`/accounts/${item.id}/`, { is_active: !item.is_active }); await loadAccounts() } catch (error: any) { ElMessage.error(error.response?.data?.detail || '更新失败') } } if (command === 'delete') { await ElMessageBox.confirm(`确定删除账号“${item.name}”吗？`, '删除账号', { type: 'warning' }).then(async () => { try { await api.delete(`/accounts/${item.id}/`); await loadAccounts(); ElMessage.success('删除成功') } catch (error: any) { ElMessage.error(error.response?.data?.detail || '删除失败') } }).catch(() => undefined) } }
onMounted(loadAccounts)
</script>
