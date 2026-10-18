<template>
  <div class="page command-page">
    <div class="page-heading">
      <div><div class="eyebrow">运维</div><h1>命令执行</h1><p>在远程机器上执行 Shell 或 Kubernetes 命令并实时查看输出。</p></div>
      <el-button :icon="Refresh" :loading="loading" @click="refreshPage" class="icon-primary">刷新</el-button>
    </div>

    <div class="settings-layout command-layout">
      <nav class="settings-nav" aria-label="命令执行分类">
        <button v-for="item in sections" :key="item.key" type="button" :class="{ active: activeSection === item.key }" :aria-pressed="activeSection === item.key" @click="activeSection = item.key"><el-icon :class="item.key === 'history' ? 'icon-purple' : 'icon-success'"><component :is="item.icon" /></el-icon>{{ item.label }}</button>
      </nav>
      <div class="settings-content">
        <section v-if="activeSection !== 'history'" class="command-workbench">
          <div class="settings-section-heading"><div><h2>{{ form.mode === 'shell' ? 'Shell' : 'K8s' }} 命令</h2><p>在远程机器上执行命令并实时查看输出。</p></div></div>
          <div class="command-form-heading"><strong>执行命令</strong><span>单台机器 · 最长 10 分钟</span></div>
          <el-form :key="form.mode" label-position="top" class="command-form" @submit.prevent="submit">
            <el-form-item label="执行机器" required>
              <el-select v-model="form.file_config_id" filterable placeholder="选择项目管理中的机器" @change="changeMachine">
                <el-option v-for="machine in machines" :key="machine.id" :label="machineLabel(machine)" :value="machine.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="执行路径" :required="form.mode === 'k8s'">
              <el-input v-model="form.working_directory" placeholder="/root" />
            </el-form-item>
            <el-form-item v-if="form.mode === 'k8s'" label="文件">
              <el-select v-model="form.remote_file_id" filterable clearable :disabled="!selectedMachine" placeholder="选择该机器文件列表中的文件（可选）" @change="changeFile">
                <el-option v-for="file in selectedMachine?.files || []" :key="file.id" :label="file.path" :value="file.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="命令内容" required class="command-content-field">
              <el-input v-model="form.command" type="textarea" :rows="5" resize="vertical" placeholder="输入要执行的命令" @input="form.commandEdited = true" />
            </el-form-item>
            <el-alert v-if="form.mode === 'shell'" class="command-safety-notice" title="已启用危险命令黑名单，删除、磁盘操作、关机重启及间接执行等命令被禁止" type="warning" :closable="false" show-icon />
            <el-alert v-if="form.submissionError" class="command-safety-notice" :title="form.submissionError" type="error" :closable="false" show-icon />
            <div class="command-submit-row">
              <span v-if="selectedMachine">目标：{{ machineLabel(selectedMachine) }}</span>
              <el-button v-if="hasPermission('command_execution.execute')" type="primary" :icon="VideoPlay" :loading="submitting" @click="submit" class="icon-success">执行命令</el-button>
            </div>
          </el-form>
        </section>

        <section v-else class="command-history">
          <div class="settings-section-heading"><div><h2>执行历史</h2><p>查看有权限访问的 Shell 和 K8s 执行记录。</p></div></div>
          <div class="command-history-filter"><span>执行类型</span><el-select v-model="historyMode" placeholder="全部" aria-label="历史执行类型" @change="filterHistory"><el-option label="全部" value="" /><el-option label="Shell" value="shell" /><el-option label="K8s" value="k8s" /></el-select></div>
          <el-table :data="executions" class="admin-table" v-loading="loading" empty-text="暂无命令执行记录" highlight-current-row @row-click="selectExecution">
            <el-table-column label="时间" min-width="170"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
            <el-table-column prop="operator" label="执行人" min-width="110" />
            <el-table-column label="机器" min-width="210"><template #default="{ row }"><strong>{{ row.host_name }}</strong><small class="table-subtext">{{ row.ip_address }}</small></template></el-table-column>
            <el-table-column label="类型" width="90"><template #default="{ row }"><el-tag effect="plain">{{ row.mode === 'k8s' ? 'K8s' : 'Shell' }}</el-tag></template></el-table-column>
            <el-table-column prop="working_directory" label="执行路径" min-width="170" show-overflow-tooltip />
            <el-table-column prop="command" label="命令" min-width="260" show-overflow-tooltip />
            <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ formatStatus(row.status) }}</el-tag></template></el-table-column>
            <el-table-column label="耗时" width="100"><template #default="{ row }">{{ elapsed(row, clock) }}</template></el-table-column>
            <el-table-column label="查看" width="72" fixed="right"><template #default="{ row }"><el-tooltip content="查看输出"><el-button text :icon="View" aria-label="查看执行输出" @click.stop="selectExecution(row)" class="icon-primary" /></el-tooltip></template></el-table-column>
          </el-table>
          <div class="command-pagination"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next" @current-change="loadExecutions" @size-change="page = 1; loadExecutions()" /></div>
        </section>
      </div>
    </div>
    <el-dialog v-model="outputVisible" title="执行输出" width="min(1100px, 94vw)" append-to-body :close-on-click-modal="false" @close="closeOutput" @closed="restoreOutputFocus" @opened="scrollTerminal">
      <div v-if="outputLoading" class="output-loading"><el-skeleton :rows="6" animated /></div>
      <el-alert v-else-if="outputError" :title="outputError" type="error" :closable="false" show-icon />
      <template v-else>
        <section class="terminal-panel">
          <div class="terminal-toolbar">
            <div class="terminal-title"><span class="terminal-lights"><i></i><i></i><i></i></span><strong>执行输出</strong><small v-if="selectedExecution">#{{ selectedExecution.id }} · {{ selectedExecution.host_name }}（{{ selectedExecution.ip_address }}）</small></div>
            <div v-if="selectedExecution" class="terminal-meta">
              <span v-if="isActive" class="stream-state"><i></i>{{ streamConnected ? '实时连接' : '正在重连' }}</span>
              <span>耗时 {{ executionElapsed }}</span>
              <span v-if="selectedExecution.exit_code !== null">退出码 {{ selectedExecution.exit_code }}</span>
              <el-tag :type="statusType(selectedExecution.status)" effect="dark">{{ statusLabels[selectedExecution.status] }}</el-tag>
              <el-button v-if="isActive && hasPermission('command_execution.execute')" size="small" type="danger" plain :loading="stopping" :disabled="selectedExecution.stop_requested" @click="stopExecution">停止</el-button>
            </div>
          </div>
          <div ref="terminalRef" class="terminal-output">
            <template v-if="selectedExecution">
              <div class="terminal-command"><span>$</span> cd {{ selectedExecution.working_directory }} && {{ selectedExecution.command }}</div>
              <pre v-for="output in selectedExecution.outputs || []" :key="output.sequence" :class="`terminal-${output.stream}`">{{ output.content }}</pre>
              <div v-if="selectedExecution.error_message" class="terminal-error-message">{{ selectedExecution.error_message }}</div>
              <span v-if="isActive" class="terminal-cursor"></span>
            </template>
            <div v-else class="terminal-empty">选择历史任务或执行一条新命令后，这里将显示实时输出。</div>
          </div>
        </section>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, VideoPlay, View, Monitor, Connection, Document } from '@element-plus/icons-vue'
import { api, type CommandExecution, type CommandMachine } from '../api'
import { hasPermission } from '../composables/useAuth'
import { useCommandStream } from '../composables/useCommandStream'
import { elapsed, statusLabels, statusType, terminalStatuses } from '../features/commands/model'
import { createCommandWorkspace, createExecutionOutput, type CommandSection } from '../features/commands/workspace'

type PageResult<T> = { count: number; page: number; page_size: number; results: T[] }
const sections: { key: CommandSection; label: string; icon: unknown }[] = [{ key: 'shell', label: 'Shell', icon: Monitor }, { key: 'k8s', label: 'K8s', icon: Connection }, { key: 'history', label: '执行历史', icon: Document }]
const workspace = createCommandWorkspace()
const { activeSection, form, historyMode, page, changeMachine } = workspace
const machines = ref<CommandMachine[]>([]), executions = ref<CommandExecution[]>([])
const loading = ref(false), submitting = ref(false), stopping = ref(false)
const pageSize = ref(20), total = ref(0)
let historyRequestId = 0
const terminalRef = ref<HTMLElement | null>(null)
let outputTrigger: HTMLElement | null = null
const clock = ref(Date.now())
let clockTimer: ReturnType<typeof setInterval> | undefined
const selectedMachine = computed(() => machines.value.find(item => item.id === form.value.file_config_id))
const selectedFile = computed(() => selectedMachine.value?.files.find(item => item.id === form.value.remote_file_id))
const isActive = computed(() => Boolean(selectedExecution.value && !terminalStatuses.includes(selectedExecution.value.status)))
const executionElapsed = computed(() => selectedExecution.value ? elapsed(selectedExecution.value, clock.value) : '0秒')
const { connected: streamConnected, connect: connectStream, disconnect: disconnectStream } = useCommandStream(() => {
  clock.value = Date.now()
  void loadExecutions(false)
})

const output = createExecutionOutput({
  load: async id => (await api.get<CommandExecution>(`/command-executions/${id}/`)).data,
  connect: connectStream,
  disconnect: disconnectStream,
})
const { visible: outputVisible, loading: outputLoading, error: outputError, execution: selectedExecution } = output
function rememberOutputFocus() { outputTrigger = document.activeElement instanceof HTMLElement ? document.activeElement : null }
function closeOutput() { output.close(); void loadExecutions(false) }
function restoreOutputFocus() { if (outputTrigger?.isConnected) outputTrigger.focus() }

function machineLabel(machine: CommandMachine) { return `${machine.project} / ${machine.host_name}（${machine.ip_address}）` }
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN') }
function formatStatus(value: keyof typeof statusLabels) { return statusLabels[value] }
function changeFile() { workspace.changeFile(selectedFile.value?.path || '') }
function filterHistory() { workspace.changeHistoryMode(); void loadExecutions() }

async function loadOptions() {
  const { data } = await api.get<{ machines: CommandMachine[] }>('/command-executions/options/')
  machines.value = data.machines
}
async function loadExecutions(showLoading = true) {
  const requestId = ++historyRequestId
  if (showLoading) loading.value = true
  try {
    const { data } = await api.get<PageResult<CommandExecution>>('/command-executions/', { params: { page: page.value, page_size: pageSize.value, ...(historyMode.value ? { mode: historyMode.value } : {}) } })
    if (requestId !== historyRequestId) return
    executions.value = data.results
    total.value = data.count
  } catch (error: any) { if (requestId === historyRequestId) ElMessage.error(error.response?.data?.detail || '加载执行历史失败') }
  finally { if (requestId === historyRequestId) loading.value = false }
}
async function refreshPage() {
  loading.value = true
  try { await Promise.all([loadOptions(), loadExecutions(false)]) }
  catch (error: any) { ElMessage.error(error.response?.data?.detail || '刷新命令执行页面失败') }
  finally { loading.value = false }
}
async function submit() {
  if (submitting.value || activeSection.value === 'history') return
  if (!form.value.file_config_id) return ElMessage.warning('请选择执行机器')
  if (form.value.mode === 'k8s' && !form.value.working_directory.trim()) return ElMessage.warning('K8s 模式必须填写执行路径')
  if (!form.value.command.trim()) return ElMessage.warning('请输入命令内容')
  const payload = workspace.payload()
  const submittedDraft = form.value
  submittedDraft.submissionError = ''
  rememberOutputFocus()
  submitting.value = true
  try {
    const { data } = await api.post<CommandExecution>('/command-executions/', payload, { timeout: 15000 })
    data.outputs = []
    output.showCreated(data)
    page.value = 1
    void loadExecutions(false)
    ElMessage.success('命令已提交')
  } catch (error: any) {
    submittedDraft.submissionError = error.response?.data?.detail || '命令提交失败'
    ElMessage.error(submittedDraft.submissionError)
  }
  finally { submitting.value = false }
}
async function selectExecution(row: CommandExecution) {
  rememberOutputFocus()
  await output.open(row.id)
}
async function stopExecution() {
  if (!selectedExecution.value || stopping.value || selectedExecution.value.stop_requested) return
  const target = selectedExecution.value
  stopping.value = true
  try {
    await api.post(`/command-executions/${target.id}/stop/`)
    target.stop_requested = true
    ElMessage.success('已发送停止请求')
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '停止命令失败') }
  finally { stopping.value = false }
}
function scrollTerminal() { if (terminalRef.value) terminalRef.value.scrollTop = terminalRef.value.scrollHeight }
watch(() => [selectedExecution.value?.id, selectedExecution.value?.outputs?.length], () => void nextTick(scrollTerminal))
onMounted(() => { void refreshPage(); clockTimer = setInterval(() => { clock.value = Date.now() }, 1000) })
onUnmounted(() => { output.close(); if (clockTimer) clearInterval(clockTimer) })
</script>

<style scoped>
.command-workbench { min-width: 0; }
.command-history-filter { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; color: #616d7c; font-size: 13px; }
.command-history-filter .el-select { width: 160px; }
.output-loading { min-height: 280px; }
.command-form-heading, .command-section-heading > div { display: flex; align-items: baseline; gap: 10px; }
.command-form-heading strong, .command-section-heading strong { color: #343b46; font-size: 15px; }
.command-form-heading span, .command-section-heading span { color: #99a2ae; font-size: 12px; }
.command-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; margin-top: 15px; }
.command-form :deep(.el-form-item) { min-width: 0; margin-bottom: 16px; }
.command-form :deep(.el-form-item__label) { color: #616d7c; font-size: 13px; }
.command-form :deep(.el-select) { width: 100%; }
.command-content-field { grid-column: 1 / -1; }
.command-safety-notice { grid-column: 1 / -1; margin-bottom: 16px; }
.command-content-field :deep(.el-textarea__inner) { font-family: Consolas, "Cascadia Code", monospace; font-size: 13px; line-height: 1.6; }
.command-submit-row { grid-column: 1 / -1; display: flex; align-items: center; justify-content: flex-end; gap: 16px; }
.command-submit-row span { min-width: 0; overflow: hidden; color: #8993a1; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.terminal-panel { margin-top: 0; overflow: hidden; border-radius: 5px; background: #151a22; box-shadow: 0 8px 22px rgb(20 28 38 / 12%); }
.terminal-toolbar { display: flex; min-height: 47px; align-items: center; justify-content: space-between; gap: 12px; padding: 0 15px; border-bottom: 1px solid #2a303b; color: #d5dae2; background: #202630; }
.terminal-title, .terminal-meta { display: flex; min-width: 0; align-items: center; gap: 10px; }
.terminal-title strong { font-size: 13px; }
.terminal-title small { overflow: hidden; color: #8792a2; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.terminal-lights { display: flex; gap: 5px; }
.terminal-lights i { width: 8px; height: 8px; border-radius: 50%; background: #ef6461; }
.terminal-lights i:nth-child(2) { background: #e9b949; }
.terminal-lights i:nth-child(3) { background: #46b979; }
.terminal-meta { flex-wrap: wrap; color: #9ba5b3; font-size: 12px; }
.stream-state { display: inline-flex; align-items: center; gap: 5px; }
.stream-state i { width: 6px; height: 6px; border-radius: 50%; background: #45c27d; box-shadow: 0 0 0 3px rgb(69 194 125 / 15%); }
.terminal-output { min-height: 280px; max-height: 440px; padding: 16px 18px; overflow: auto; color: #d7dce5; background: #151a22; font-family: Consolas, "Cascadia Code", monospace; font-size: 13px; line-height: 1.55; }
.terminal-output pre { display: inline; margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; letter-spacing: 0; }
.terminal-command { margin-bottom: 10px; color: #dce3ed; white-space: pre-wrap; overflow-wrap: anywhere; }
.terminal-command span { color: #55ce8a; }
.terminal-stderr, .terminal-error-message { color: #ff7b7b; }
.terminal-error-message { margin-top: 9px; }
.terminal-empty { display: grid; min-height: 245px; place-items: center; color: #697484; font-family: inherit; }
.terminal-cursor { display: inline-block; width: 7px; height: 15px; margin-left: 2px; background: #dce3ed; animation: terminal-blink 1s step-end infinite; vertical-align: text-bottom; }
@keyframes terminal-blink { 50% { opacity: 0; } }
.command-history { min-width: 0; }
.table-subtext { display: block; margin-top: 3px; color: #929ba7; font-size: 12px; }
.command-pagination { max-width: 100%; overflow-x: auto; display: flex; justify-content: flex-end; padding-top: 16px; }
@media (max-width: 700px) { .command-form { grid-template-columns: 1fr; } .command-content-field, .command-submit-row { grid-column: 1; } .terminal-toolbar { align-items: flex-start; flex-direction: column; padding-block: 10px; } .terminal-meta { flex-wrap: wrap; } }
</style>
