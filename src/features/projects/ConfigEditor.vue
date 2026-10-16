<template>
  <el-dialog :model-value="modelValue" :title="config ? '编辑主机配置' : '新增主机配置'" width="560px" :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="close">
    <el-form ref="formRef" :model="form" :rules="rules" :disabled="saving" label-position="top" @submit.prevent="save">
      <el-row :gutter="16">
        <el-col :span="12"><el-form-item label="项目" prop="project_id"><el-tree-select v-model="form.project_id" :data="tree" node-key="id" check-strictly :render-after-expand="false" filterable placeholder="选择项目" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="节点名称" prop="host_name"><el-input v-model="form.host_name" maxlength="150" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="IP 地址" prop="ip_address"><el-input v-model="form.ip_address" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="SSH 端口" prop="port"><el-input-number v-model="form.port" :min="1" :max="65535" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="关联账号" prop="account_id"><el-select v-model="form.account_id" filterable><el-option v-for="account in accounts" :key="account.id" :value="account.id" :label="account.name" :disabled="!account.is_active" /></el-select></el-form-item></el-col>
      </el-row>
      <p class="muted-cell">账号保存后仅对当前配置生效；验证 SSH 时会自动读取机器名称和规格。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
    </el-form>
    <template #footer><el-button :disabled="saving" @click="close()">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </el-dialog>
</template>
<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { api } from '../../api'
import { errorText, projectTree, type Project } from './model'
interface Editable { id: number; revision: number; project_id: number; host_name: string; ip_address: string; port: number; account_id: number }
const props = defineProps<{ modelValue: boolean; config: Editable | null; projectId?: number | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [] }>()
const projects = ref<Project[]>([]), accounts = ref<{ id: number; name: string; is_active: boolean }[]>([])
const tree = computed(() => projectTree(projects.value))
const saving = ref(false), error = ref(''), formRef = ref<FormInstance>()
const form = reactive({ project_id: undefined as number | undefined, host_name: '', ip_address: '', port: 22, account_id: undefined as number | undefined })
const rules: FormRules = Object.fromEntries(['project_id', 'host_name', 'ip_address', 'account_id', 'port'].map(key => [key, [{ required: true, message: '请填写此项', trigger: 'blur' }]]))
watch(() => props.modelValue, async value => {
  if (!value) return
  error.value = ''
  const c = props.config
  Object.assign(form, c ? { project_id: c.project_id, host_name: c.host_name, ip_address: c.ip_address, port: c.port, account_id: c.account_id } : { project_id: props.projectId ?? undefined, host_name: '', ip_address: '', port: 22, account_id: undefined })
  await nextTick(); formRef.value?.clearValidate()
  try { const [p, a] = await Promise.all([api.get('/projects/'), api.get('/accounts/options/')]); projects.value = p.data; accounts.value = a.data }
  catch (e) { error.value = errorText(e) }
})
function close(done?: () => void) { if (!saving.value) { emit('update:modelValue', false); done?.() } }
async function save() {
  if (saving.value || !await formRef.value?.validate().catch(() => false)) return
  saving.value = true; error.value = ''
  try {
    if (props.config) await api.patch(`/file-configs/${props.config.id}/`, { ...form, revision: props.config.revision })
    else await api.post('/file-configs/', form)
    ElMessage.success('保存成功'); emit('saved'); emit('update:modelValue', false)
  } catch (e) { error.value = errorText(e) }
  finally { saving.value = false }
}
</script>
