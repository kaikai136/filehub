<template>
  <div class="page role-page">
    <div class="page-heading">
      <div><div class="eyebrow">系统管理</div><h1>角色管理</h1><p>配置角色权限，查看关联用户。</p></div>
      <el-button v-if="hasPermission('roles.create')" type="primary" :icon="Plus" @click="openEditor(null)" class="icon-success">新增角色</el-button>
    </div>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />
    <el-table :data="roles" class="admin-table" v-loading="loading">
      <el-table-column prop="name" label="角色名称" min-width="140" />
      <el-table-column prop="code" label="角色标识" min-width="160" />
      <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag effect="plain" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag></template></el-table-column>
      <el-table-column label="用户数据" width="130"><template #default="{ row }"><el-button text type="primary" @click="showUsers(row)">{{ row.user_count }} 名用户</el-button></template></el-table-column>
      <el-table-column label="权限管理" width="140"><template #default="{ row }"><el-button text type="primary" @click="openEditor(row)">{{ row.permissions.length }} 项权限</el-button></template></el-table-column>
      <el-table-column label="操作" width="140"><template #default="{ row }"><div class="admin-actions">
        <el-tooltip :content="row.is_builtin ? '内置角色不可编辑' : !canManageRole(row) ? '不能管理权限更高的角色' : '编辑角色'"><span><el-button v-if="hasPermission('roles.edit')" text :icon="EditPen" aria-label="编辑角色" :disabled="row.is_builtin || !canManageRole(row) || saving" @click="openEditor(row)" class="icon-primary" /></span></el-tooltip>
        <el-tooltip :content="row.is_builtin ? '内置角色不可停用' : '切换角色状态'"><span><el-button v-if="hasPermission('roles.edit')" text :icon="row.is_active ? VideoPause : VideoPlay" :aria-label="row.is_active ? '禁用角色' : '启用角色'" :disabled="row.is_builtin || !canManageRole(row) || saving" @click="toggleRole(row)" :class="{ 'icon-danger': row.is_active, 'icon-success': !(row.is_active) }" /></span></el-tooltip>
        <el-tooltip :content="row.is_builtin ? '内置角色不可删除' : row.user_count ? '请先移除关联用户' : '删除角色'"><span><el-button v-if="hasPermission('roles.delete')" text type="danger" :icon="Delete" aria-label="删除角色" :disabled="row.is_builtin || !canManageRole(row) || !!row.user_count || saving" @click="deleteRole(row)" class="icon-danger" /></span></el-tooltip>
      </div></template></el-table-column>
    </el-table>
    <el-dialog v-model="dialogVisible" :title="readOnly ? '查看角色权限' : editing ? '编辑角色' : '新增角色'" width="860px" :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="beforeClose" @closed="clearValidation">
      <el-alert v-if="readOnly" title="当前角色只能查看，修改需要角色编辑权限。" type="info" :closable="false" />
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="saving || readOnly">
        <el-form-item label="角色名称" prop="name"><el-input v-model="form.name" maxlength="100" /></el-form-item>
        <el-form-item label="角色标识" prop="code"><el-input v-model="form.code" :disabled="!!editing" maxlength="100" placeholder="小写字母、数字和下划线" /></el-form-item>
        <el-form-item label="权限管理">
          <div class="permission-matrix">
            <div class="permission-matrix-row permission-matrix-header"><strong>模块</strong><span v-for="action in actions" :key="action">{{ actionLabels[action] }}</span></div>
            <div v-for="group in groups" :key="group.key" class="permission-matrix-row">
              <div class="permission-module"><el-checkbox :model-value="isGroupSelected(group)" :indeterminate="isGroupIndeterminate(group)" @change="(checked: boolean | string | number) => toggleGroup(group, Boolean(checked))">{{ group.label }}</el-checkbox></div>
              <div v-for="action in actions" :key="action" class="permission-cell">
                <el-checkbox v-if="group.permissions.some(permission => permission.action === action)" :model-value="form.permissions.includes(`${group.key}.${action}`)" :disabled="!canAssignPermission(`${group.key}.${action}`)" @change="(checked: boolean | string | number) => setPermission(`${group.key}.${action}`, Boolean(checked))" />
                <span v-else class="permission-empty">—</span>
              </div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="状态"><el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="saving" @click="dialogVisible = false">{{ readOnly ? '关闭' : '取消' }}</el-button><el-button v-if="!readOnly" type="primary" :loading="saving" @click="saveRole">保存</el-button></template>
    </el-dialog>
    <el-dialog v-model="membersVisible" :title="(memberRole?.name || '') + ' · 用户数据'" width="540px">
      <el-alert v-if="memberError" :title="memberError" type="error" :closable="false" />
      <el-table :data="members" v-loading="membersLoading"><el-table-column prop="username" label="登录名" /><el-table-column prop="name" label="姓名" /><el-table-column label="状态"><template #default="{ row }"><el-tag effect="plain" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag></template></el-table-column></el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, EditPen, Plus, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import { api } from '../api'
import { authUser, hasPermission, refreshAuth } from '../composables/useAuth'
import { changePermission } from '../features/access/model'

type Permission = { key: string; module: string; module_label: string; action: string; action_label: string }
type Role = { id: number; name: string; code: string; is_active: boolean; permissions: string[]; is_builtin: boolean; user_count: number }
type Member = { id: number; username: string; name: string; is_active: boolean }
type Group = { key: string; label: string; permissions: Permission[] }

const actions = ['view', 'create', 'edit', 'delete', 'execute', 'import', 'export'] as const
const actionLabels: Record<string, string> = { view: '查看', create: '新增', edit: '编辑', delete: '删除', execute: '执行', import: '导入', export: '导出' }
const roles = ref<Role[]>([]), catalog = ref<Permission[]>([]), members = ref<Member[]>([]), memberRole = ref<Role | null>(null)
const membersVisible = ref(false), membersLoading = ref(false), memberError = ref(''), dialogVisible = ref(false), readOnly = ref(false), saving = ref(false), loading = ref(false), errorMessage = ref(''), editing = ref<Role | null>(null), formRef = ref<FormInstance>()
const form = reactive({ name: '', code: '', permissions: [] as string[], is_active: true })
const rules: FormRules = { name: [{ required: true, whitespace: true, message: '请输入角色名称', trigger: 'blur' }], code: [{ required: true, pattern: /^[a-z0-9_]+$/, message: '只能使用小写字母、数字和下划线', trigger: 'blur' }] }
const groups = computed<Group[]>(() => [...new Set(catalog.value.map(item => item.module))].map(key => ({ key, label: catalog.value.find(item => item.module === key)!.module_label, permissions: catalog.value.filter(item => item.module === key) })))

async function load() { loading.value = true; errorMessage.value = ''; try { const [r, p] = await Promise.all([api.get<Role[]>('/roles/'), api.get<Permission[]>('/permissions/')]); roles.value = r.data; catalog.value = p.data } catch (error: any) { errorMessage.value = error.response?.data?.detail || '加载角色失败' } finally { loading.value = false } }
function clearValidation() { nextTick(() => formRef.value?.clearValidate()) }
function openEditor(role: Role | null) { editing.value = role; readOnly.value = role ? Boolean(role.is_builtin || !hasPermission('roles.edit') || !canManageRole(role)) : !hasPermission('roles.create'); Object.assign(form, role ? { name: role.name, code: role.code, permissions: [...role.permissions], is_active: role.is_active } : { name: '', code: '', permissions: [], is_active: true }); dialogVisible.value = true; clearValidation() }
function setPermission(key: string, checked: boolean) { form.permissions = changePermission(form.permissions, key, checked) }
function canManageRole(role: Role) { return Boolean(authUser.value?.is_superuser || role.permissions.every(permission => authUser.value?.permissions.includes(permission))) }
function canAssignPermission(permission: string) { return Boolean(authUser.value?.is_superuser || authUser.value?.permissions.includes(permission)) }
function isGroupSelected(group: Group) { const keys = group.permissions.map(permission => permission.key); return keys.length > 0 && keys.every(key => form.permissions.includes(key)) }
function isGroupIndeterminate(group: Group) { const keys = group.permissions.map(permission => permission.key); const selected = keys.filter(key => form.permissions.includes(key)).length; return selected > 0 && selected < keys.length }
function toggleGroup(group: Group, checked: boolean) { for (const permission of group.permissions) if (canAssignPermission(permission.key)) setPermission(permission.key, checked) }
async function saveRole() { if (saving.value || readOnly.value || !await formRef.value?.validate().catch(() => false)) return; saving.value = true; try { const payload = { ...form, permissions: [...form.permissions] }; if (editing.value) await api.patch('/roles/' + editing.value.id + '/', payload); else await api.post('/roles/', payload); dialogVisible.value = false; ElMessage.success('保存成功'); await load(); await refreshAuth().catch(() => undefined) } catch (error: any) { ElMessage.error(error.response?.data?.detail || '保存失败') } finally { saving.value = false } }
async function toggleRole(role: Role) { if (saving.value) return; saving.value = true; try { await api.patch('/roles/' + role.id + '/', { is_active: !role.is_active }); await load(); await refreshAuth().catch(() => undefined) } catch (error: any) { ElMessage.error(error.response?.data?.detail || '更新失败') } finally { saving.value = false } }
async function deleteRole(role: Role) { try { await ElMessageBox.confirm('确定删除角色“' + role.name + '”吗？', '删除角色', { type: 'warning' }) } catch { return }; saving.value = true; try { await api.delete('/roles/' + role.id + '/'); await load(); await refreshAuth().catch(() => undefined); ElMessage.success('删除成功') } catch (error: any) { ElMessage.error(error.response?.data?.detail || '删除失败') } finally { saving.value = false } }
let memberVersion = 0
async function showUsers(role: Role) { const version = ++memberVersion; memberRole.value = role; members.value = []; memberError.value = ''; membersVisible.value = true; membersLoading.value = true; try { const { data } = await api.get<Member[]>('/roles/' + role.id + '/users/'); if (version === memberVersion) members.value = data } catch (error: any) { if (version === memberVersion) memberError.value = error.response?.data?.detail || '加载成员失败' } finally { if (version === memberVersion) membersLoading.value = false } }
function beforeClose(done: () => void) { if (!saving.value) done() }
onMounted(load)
</script>
