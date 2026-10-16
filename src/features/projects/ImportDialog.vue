<template>
  <el-dialog v-model="visible" title="Excel 导入主机配置" width="800px" :close-on-click-modal="false" :close-on-press-escape="!busy" :before-close="close">
    <p>使用模板填写项目完整路径和已有账号名称。重复配置会跳过，存在错误时不会写入。</p>
    <div class="transfer-controls"><el-button :disabled="busy" @click="downloadTemplate">下载模板</el-button><input :disabled="busy" type="file" accept=".xlsx" aria-label="选择 Excel 文件" @change="upload" /></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="rows" max-height="380" v-loading="busy">
      <el-table-column prop="row" label="行" width="65" /><el-table-column prop="project_path" label="项目" /><el-table-column prop="host_name" label="节点名称" />
      <el-table-column label="校验结果"><template #default="{ row }"><el-tag :type="row.status === 'error' ? 'danger' : row.status === 'duplicate' ? 'warning' : 'success'">{{ row.status === 'error' ? '错误' : row.status === 'duplicate' ? '重复，跳过' : '可导入' }}</el-tag></template></el-table-column>
      <el-table-column prop="error" label="说明" min-width="200" />
    </el-table>
    <template #footer><span>共 {{ rows.length }} 行</span><el-button :disabled="busy" @click="close()">关闭</el-button><el-button type="primary" :loading="busy" :disabled="!canImport(rows, token)" @click="confirm">确认导入</el-button></template>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../../api'
import { canImport, errorText, type ImportRow } from './model'
const emit = defineEmits<{ imported: [] }>()
const visible = ref(false), busy = ref(false), error = ref(''), rows = ref<ImportRow[]>([]), token = ref<string | null>(null)
function open() { rows.value = []; token.value = null; error.value = ''; visible.value = true }
function close(done?: () => void) { if (!busy.value) { visible.value = false; done?.() } }
function saveBlob(blob: Blob, name: string) { const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000) }
async function downloadTemplate() { try { const r = await api.get('/file-configs/import-template/', { responseType: 'blob' }); saveBlob(r.data, '主机导入模板.xlsx') } catch (e) { error.value = errorText(e) } }
async function upload(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  if (!file || busy.value) return
  busy.value = true; token.value = null; rows.value = []; error.value = ''
  try { const form = new FormData(); form.append('file', file); const r = await api.post('/file-configs/import/', form, { timeout: 60000 }); rows.value = r.data.rows; token.value = r.data.token }
  catch (e) { error.value = errorText(e) }
  finally { busy.value = false; input.value = '' }
}
async function confirm() {
  if (busy.value || !canImport(rows.value, token.value)) return
  busy.value = true
  try { const r = await api.post('/file-configs/import/', { token: token.value }, { timeout: 60000 }); ElMessage.success(`新增 ${r.data.created} 条，跳过 ${r.data.skipped} 条`); visible.value = false; emit('imported') }
  catch (e: any) { error.value = errorText(e); token.value = null; if (e.response?.data?.rows) rows.value = e.response.data.rows }
  finally { busy.value = false }
}
defineExpose({ open })
</script>
<style scoped>.transfer-controls { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }</style>
