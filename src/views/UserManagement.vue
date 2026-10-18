<template>
  <div class="page user-page">
    <div class="page-heading"><div><div class="eyebrow">系统管理</div><h1>用户管理</h1><p>管理登录用户和角色。</p></div><el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button></div>
    <div class="module-toolbar"><el-input v-model="query" :prefix-icon="Search" placeholder="搜索登录名或姓名" clearable /><span class="toolbar-count">共 {{ filteredUsers.length }} 个用户</span></div>
    <el-table :data="filteredUsers" class="admin-table" v-loading="loading">
      <el-table-column prop="username" label="登录名" min-width="150" />
      <el-table-column prop="name" label="姓名" min-width="150" />
      <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag effect="plain" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag></template></el-table-column>
      <el-table-column label="最近登录时间" min-width="200"><template #default="{ row }">{{ row.last_login ? new Date(row.last_login).toLocaleString('zh-CN') : '从未登录' }}</template></el-table-column>
      <el-table-column label="双因素认证" min-width="190"><template #default="{ row }">
        <span v-if="row.two_factor_status === 'required'" class="two-factor-pending">待验证</span>
        <template v-else>
          <el-switch v-if="row.username !== 'admin' && row.id !== currentUser?.id" :model-value="row.two_factor_status === 'enabled'" inline-prompt active-text="开" inactive-text="关" :disabled="saving" @change="toggleTwoFactor(row)" />
          <el-tag v-else :type="row.two_factor_status === 'enabled' ? 'success' : 'info'">{{ row.two_factor_status === 'enabled' ? '已启用' : '未启用' }}</el-tag>
          <el-button v-if="row.two_factor_status === 'enabled' && row.username !== 'admin' && row.id !== currentUser?.id" text type="primary" :disabled="saving" @click="resetTwoFactor(row)">重置</el-button>
        </template>
      </template></el-table-column>
      <el-table-column label="操作" width="140"><template #default="{ row }"><div class="admin-actions">
        <el-tooltip content="编辑用户"><el-button text :icon="EditPen" aria-label="编辑用户" :disabled="saving" @click="openEdit(row)" /></el-tooltip>
        <el-tooltip :content="row.id === currentUser?.id ? '不能停用当前用户' : row.is_active ? '禁用用户' : '启用用户'"><span><el-button text :icon="row.is_active ? VideoPause : VideoPlay" :aria-label="row.is_active ? '禁用用户' : '启用用户'" :disabled="saving || row.id === currentUser?.id" @click="toggleUser(row)" /></span></el-tooltip>
        <el-tooltip :content="row.id === currentUser?.id ? '不能删除当前用户' : '删除用户'"><span><el-button text type="danger" :icon="Delete" aria-label="删除用户" :disabled="saving || row.id === currentUser?.id" @click="deleteUser(row)" /></span></el-tooltip>
      </div></template></el-table-column>
    </el-table>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑用户' : '新增用户'" width="500px" :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="beforeClose" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" :disabled="saving">
        <el-form-item label="登录名" prop="username"><el-input v-model="form.username" :disabled="!!editing" maxlength="150" /></el-form-item>
        <el-form-item label="姓名" prop="name"><el-input v-model="form.name" maxlength="150" /></el-form-item>
        <el-form-item label="邮箱" prop="email"><el-input v-model="form.email" maxlength="254" /></el-form-item>
        <el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" show-password autocomplete="new-password" :placeholder="editing ? '留空表示不修改' : '至少 6 位'" /></el-form-item>
        <el-form-item label="角色" prop="role_ids"><el-select v-model="form.role_ids" multiple filterable style="width:100%" placeholder="选择角色"><el-option v-for="role in roles" :key="role.id" :label="role.name + (role.is_active ? '' : '（已禁用）')" :value="role.id" :disabled="!role.is_active && !editing?.roles.some(r => r.id === role.id)" /></el-select></el-form-item>
        <el-form-item label="状态"><el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" :disabled="editing?.id === currentUser?.id" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="saving" @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveUser">保存</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, EditPen, Plus, Search, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import { api, type User } from '../api'
import { authUser as currentUser } from '../composables/useAuth'
type Role = { id: number; name: string; code: string; is_active: boolean }
const users = ref<User[]>([]), roles = ref<Role[]>([]), query = ref(''), loading = ref(false), errorMessage = ref(''), dialogVisible = ref(false), saving = ref(false), editing = ref<User | null>(null), formRef = ref<FormInstance>()
const defaults = () => ({ username: '', name: '', email: '', password: '', role_ids: [] as number[], is_active: true })
const form = reactive(defaults())
const formRules: FormRules = { username: [{ required: true, whitespace: true, message: '请输入登录名', trigger: 'blur' }], name: [{ required: true, whitespace: true, message: '请输入姓名', trigger: 'blur' }], email: [{ type: 'email', message: '邮箱格式无效', trigger: 'blur' }], password: [{ validator: (_rule, value, callback) => (!editing.value && !value ? callback(new Error('请输入密码')) : value && value.length < 6 ? callback(new Error('密码至少 6 位')) : callback()), trigger: 'blur' }], role_ids: [{ validator: (_rule, value, callback) => (!editing.value && (!Array.isArray(value) || !value.length) ? callback(new Error('请至少选择一个角色')) : callback()), trigger: 'change' }] }
const filteredUsers = computed(() => users.value.filter(user => `${user.username} ${user.name}`.toLowerCase().includes(query.value.toLowerCase())))
async function load() { loading.value = true; errorMessage.value = ''; try { const [u, r] = await Promise.all([api.get<User[]>('/users/'), api.get<Role[]>('/roles/')]); users.value = u.data; roles.value = r.data } catch (error: any) { errorMessage.value = error.response?.data?.detail || '加载用户失败' } finally { loading.value = false } }
function openCreate() { resetForm(); dialogVisible.value = true }
function openEdit(user: User) { editing.value = user; Object.assign(form, { username: user.username, name: user.name, email: user.email, password: '', role_ids: user.roles.map(role => role.id), is_active: user.is_active }); dialogVisible.value = true; nextTick(() => formRef.value?.clearValidate()) }
async function saveUser() { if (saving.value || !await formRef.value?.validate().catch(() => false)) return; saving.value = true; try { const payload = { ...form, role_ids: [...form.role_ids] }; if (editing.value) await api.patch(`/users/${editing.value.id}/`, payload); else await api.post('/users/', payload); dialogVisible.value = false; ElMessage.success('保存成功'); await load() } catch (error: any) { ElMessage.error(error.response?.data?.detail || '保存失败') } finally { saving.value = false } }
async function toggleUser(user: User) { if (saving.value) return; saving.value = true; try { await api.patch(`/users/${user.id}/`, { is_active: !user.is_active }); await load(); ElMessage.success('状态已更新') } catch (error: any) { ElMessage.error(error.response?.data?.detail || '更新失败') } finally { saving.value = false } }
async function deleteUser(user: User) { try { await ElMessageBox.confirm(`确定删除用户“${user.username}”吗？删除后不可恢复。`, '删除用户', { type: 'warning' }) } catch { return }; saving.value = true; try { await api.delete(`/users/${user.id}/`); await load(); ElMessage.success('删除成功') } catch (error: any) { ElMessage.error(error.response?.data?.detail || '删除失败') } finally { saving.value = false } }
function beforeClose(done: () => void) { if (!saving.value) done() }
async function toggleTwoFactor(user: User) {
  if (saving.value || user.username === 'admin' || user.id === currentUser.value?.id) return
  const enabled = user.two_factor_status !== 'enabled'
  saving.value = true
  try {
    await api.post(`/users/${user.id}/two-factor/${enabled ? 'enable' : 'disable'}/`)
    ElMessage.success(enabled ? '已开启双因素认证，用户下次登录需要绑定' : '已关闭双因素认证')
    await load()
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '更新双因素认证失败') } finally { saving.value = false }
}
async function resetTwoFactor(user: User) {
  try { await ElMessageBox.confirm(`重置“${user.username}”的双因素认证后，用户下次登录需要重新扫码绑定。当前登录会话不会被撤销。`, '重置双因素认证', { type: 'warning', confirmButtonText: '确认重置', cancelButtonText: '取消' }) } catch { return }
  saving.value = true
  try {
    await api.post(`/users/${user.id}/two-factor/reset/`)
    ElMessage.success('双因素认证已重置')
    await load()
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '重置失败') } finally { saving.value = false }
}
function resetForm() { Object.assign(form, defaults()); editing.value = null; nextTick(() => formRef.value?.clearValidate()) }
onMounted(load)
</script>
