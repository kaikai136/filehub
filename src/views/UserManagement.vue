<template>
  <div class="page user-page">
    <div class="page-heading">
      <div><div class="eyebrow">系统管理</div><h1>用户管理</h1><p>管理可以访问 ConfigHub 的用户和权限。</p></div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
    </div>
    <div class="module-toolbar"><el-input v-model="query" :prefix-icon="Search" placeholder="搜索用户名或邮箱" clearable /><span class="toolbar-count">共 {{ filteredUsers.length }} 个用户</span></div>
    <div class="resource-list user-list">
      <div class="user-row user-header"><span>用户</span><span>角色</span><span>状态</span><span>最近登录</span><span></span></div>
      <div v-for="user in filteredUsers" :key="user.id" class="user-row">
        <div class="resource-main"><span class="user-avatar">{{ (user.name || user.username).slice(0, 1).toUpperCase() }}</span><div><strong>{{ user.name || user.username }}</strong><small>{{ user.username }} · {{ user.email || '未设置邮箱' }}</small></div></div>
        <el-tag size="small" effect="plain" :type="user.is_superuser ? 'warning' : user.is_staff ? 'primary' : 'info'">{{ user.is_superuser ? '超级管理员' : user.is_staff ? '管理员' : '普通用户' }}</el-tag>
        <el-tag size="small" effect="plain" :type="user.is_active ? 'success' : 'info'">{{ user.is_active ? '启用' : '禁用' }}</el-tag>
        <span class="resource-updated">{{ user.last_login ? formatDate(user.last_login) : '从未登录' }}</span>
        <el-dropdown @command="(command: string | number | object) => handleCommand(String(command), user)">
          <el-button text :icon="MoreFilled" />
          <template #dropdown><el-dropdown-menu><el-dropdown-item command="edit">编辑</el-dropdown-item><el-dropdown-item command="toggle">{{ user.is_active ? '禁用' : '启用' }}</el-dropdown-item><el-dropdown-item command="delete" divided>删除</el-dropdown-item></el-dropdown-menu></template>
        </el-dropdown>
      </div>
      <el-empty v-if="!filteredUsers.length" description="没有找到用户" />
    </div>
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑用户' : '新增用户'" width="460px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top">
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" :disabled="!!editing" placeholder="请输入用户名" /></el-form-item>
        <el-form-item label="显示名称"><el-input v-model="form.name" placeholder="请输入显示名称" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" placeholder="请输入邮箱" /></el-form-item>
        <el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" show-password :placeholder="editing ? '留空表示不修改' : '至少 6 位'" /></el-form-item>
        <el-form-item v-if="!editing" label="角色"><el-radio-group v-model="form.is_staff"><el-radio :value="false">普通用户</el-radio><el-radio :value="true">管理员</el-radio></el-radio-group></el-form-item>
        <el-form-item label="状态"><el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveUser">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { MoreFilled, Plus, Search } from '@element-plus/icons-vue'
import { api, type User } from '../api'

const users = ref<User[]>([])
const query = ref('')
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref<User | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ username: '', name: '', email: '', password: '', is_staff: false, is_active: true })
const formRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ validator: (_rule, value, callback) => (!editing.value && !value ? callback(new Error('请输入密码')) : callback()), trigger: 'blur' }],
}
const filteredUsers = computed(() => users.value.filter((user) => `${user.username} ${user.name} ${user.email}`.toLowerCase().includes(query.value.toLowerCase())))
async function loadUsers() {
  try { users.value = (await api.get<User[]>('/users/')).data }
  catch (error: any) { ElMessage.error(error.response?.data?.detail || '加载用户失败') }
}
function openCreate() { editing.value = null; dialogVisible.value = true }
function openEdit(user: User) { editing.value = user; Object.assign(form, { username: user.username, name: user.name, email: user.email, password: '', is_staff: user.is_staff, is_active: user.is_active }); dialogVisible.value = true }
async function saveUser() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editing.value) await api.patch(`/users/${editing.value.id}/`, form)
    else await api.post('/users/', form)
    ElMessage.success('保存成功'); dialogVisible.value = false; await loadUsers()
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '保存失败') } finally { saving.value = false }
}
async function handleCommand(command: string, user: User) {
  if (command === 'edit') return openEdit(user)
  if (command === 'toggle') {
    try { await api.patch(`/users/${user.id}/`, { is_active: !user.is_active }); await loadUsers(); ElMessage.success('状态已更新') }
    catch (error: any) { ElMessage.error(error.response?.data?.detail || '更新失败') }
  }
  if (command === 'delete') {
    await ElMessageBox.confirm(`确定删除用户“${user.username}”吗？删除后不可恢复。`, '删除用户', { type: 'warning' })
      .then(async () => { await api.delete(`/users/${user.id}/`); await loadUsers(); ElMessage.success('删除成功') }).catch(() => undefined)
  }
}
function resetForm() { Object.assign(form, { username: '', name: '', email: '', password: '', is_staff: false, is_active: true }); editing.value = null }
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
onMounted(loadUsers)
</script>
