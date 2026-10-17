<template>
  <div class="page command-page">
    <div class="page-heading">
      <div><div class="eyebrow">运维</div><h1>命令执行</h1><p>在远程机器上执行 Shell 或 Kubernetes 命令并实时查看输出。</p></div>
      <el-button :icon="Refresh" :loading="loading" @click="refreshPage">刷新</el-button>
    </div>

    <section class="command-workbench">
      <div class="command-form-heading"><strong>执行命令</strong><span>单台机器 · 最长 10 分钟</span></div>
      <el-form label-position="top" class="command-form" @submit.prevent="submit">
        <el-form-item label="执行类型">
          <el-segmented v-model="form.mode" :options="modeOptions" @change="changeMode" />
        </el-form-item>
        <el-form-item label="执行机器" required>
          <el-select v-model="form.file_config_id" filterable placeholder="选择项目管理中的机器" @change="changeMachine">
            <el-option v-for="machine in machines" :key="machine.id" :label="machineLabel(machine)" :value="machine.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行路径" :required="form.mode === 'k8s'">
          <el-input v-model="form.working_directory" placeholder="/root" />
        </el-form-item>
        <el-form-item label="文件">
          <el-select v-model="form.remote_file_id" filterable clearable :disabled="!selectedMachine" placeholder="选择该机器文件列表中的文件（可选）" @change="changeFile">
            <el-option v-for="file in selectedMachine?.files || []" :key="file.id" :label="file.path" :value="file.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="命令内容" required class="command-content-field">
          <el-input v-model="form.command" type="textarea" :rows="5" resize="vertical" placeholder="输入要执行的命令" @input="commandEdited = true" />
        </el-form-item>
        <div class="command-submit-row">
          <span v-if="selectedMachine">目标：{{ machineLabel(selectedMachine) }}</span>
          <el-button v-if="hasPermission('command_execution.execute')" type="primary" :icon="VideoPlay" :loading="submitting" @click="submit">执行命令</el-button>
        </div>
      </el-form>
    </section>

    <section class="terminal-panel">
      <div class="terminal-toolbar">
        <div class="terminal-title"><span class="terminal-lights"><i></i><i></i><i></i></span><strong>执行输出</strong><small v-if="selectedExecution">#{{ selectedExecution.id }} · {{ selectedExecution.host_name }}（{{ selectedExecution.ip_address }}）</small></div>
        <div v-if="selectedExecution" class="terminal-meta">
          <span v-if="isActive" class="stream-state"><i></i>{{ streamConnected ? '实时连接' : '正在重连' }}</span>
          <span>耗时 {{ executionElapsed }}</span>
          <span v-if="selectedExecution.exit_code !== null">退出码 {{ selectedExecution.exit_code }}</span>
          <el-tag :type="statusType(selectedExecution.status)" effect="dark">{{ statusLabels[selectedExecution.status] }}</el-tag>
          <el-button v-if="isActive && hasPermission('command_execution.execute')" size="small" type="danger" plain :loading="stopping" @click="stopExecution">停止</el-button>
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

    <section class="command-history">
      <div class="command-section-heading"><div><strong>执行历史</strong><span>仅显示当前用户创建的任务</span></div></div>
      <el-table :data="executions" class="admin-table" v-loading="loading" empty-text="暂无命令执行记录" highlight-current-row @row-click="selectExecution">
        <el-table-column label="时间" min-width="170"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
        <el-table-column prop="operator" label="执行人" min-width="110" />
        <el-table-column label="机器" min-width="210"><template #default="{ row }"><strong>{{ row.host_name }}</strong><small class="table-subtext">{{ row.ip_address }}</small></template></el-table-column>
        <el-table-column label="类型" width="90"><template #default="{ row }"><el-tag effect="plain">{{ row.mode === 'k8s' ? 'K8s' : 'Shell' }}</el-tag></template></el-table-column>
        <el-table-column prop="working_directory" label="执行路径" min-width="170" show-overflow-tooltip />
        <el-table-column prop="command" label="命令" min-width="260" show-overflow-tooltip />
        <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ formatStatus(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="耗时" width="100"><template #default="{ row }">{{ elapsed(row, clock) }}</template></el-table-column>
        <el-table-column label="查看" width="72" fixed="right"><template #default="{ row }"><el-tooltip content="查看输出"><el-button text :icon="View" aria-label="查看执行输出" @click.stop="selectExecution(row)" /></el-tooltip></template></el-table-column>
      </el-table>
      <div class="command-pagination"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next" @current-change="loadExecutions" @size-change="page = 1; loadExecutions()" /></div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, VideoPlay, View } from '@element-plus/icons-vue'
import { api, type CommandExecution, type CommandMachine } from '../api'
import { hasPermission } from '../composables/useAuth'
import { useCommandStream } from '../composables/useCommandStream'
import { defaultK8sCommand, elapsed, statusLabels, statusType, terminalStatuses } from '../features/commands/model'

type PageResult<T> = { count: number; page: number; page_size: number; results: T[] }
const modeOptions = [{ label: 'Shell', value: 'shell' }, { label: 'K8s', value: 'k8s' }]
const machines = ref<CommandMachine[]>([]), executions = ref<CommandExecution[]>([])
const loading = ref(false), submitting = ref(false), stopping = ref(false)
const page = ref(1), pageSize = ref(20), total = ref(0)
const selectedExecution = ref<CommandExecution | null>(null), terminalRef = ref<HTMLElement | null>(null)
const commandEdited = ref(false), generatedCommand = ref(''), clock = ref(Date.now())
let clockTimer: ReturnType<typeof setInterval> | undefined
const form = reactive<{ mode: 'shell' | 'k8s'; file_config_id: number | null; working_directory: string; remote_file_id: number | null; command: string }>({
  mode: 'shell', file_config_id: null, working_directory: '/root', remote_file_id: null, command: '',
})
const selectedMachine = computed(() => machines.value.find(item => item.id === form.file_config_id))
const selectedFile = computed(() => selectedMachine.value?.files.find(item => item.id === form.remote_file_id))
const isActive = computed(() => Boolean(selectedExecution.value && !terminalStatuses.includes(selectedExecution.value.status)))
const executionElapsed = computed(() => selectedExecution.value ? elapsed(selectedExecution.value, clock.value) : '0秒')
const { connected: streamConnected, connect: connectStream, disconnect: disconnectStream } = useCommandStream(() => {
  clock.value = Date.now()
  void loadExecutions(false)
})

function machineLabel(machine: CommandMachine) { return `${machine.project} / ${machine.host_name}（${machine.ip_address}）` }
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN') }
function formatStatus(value: keyof typeof statusLabels) { return statusLabels[value] }
function changeMode() {
  if (form.mode === 'shell' && !form.working_directory) form.working_directory = '/root'
  form.remote_file_id = null
  generatedCommand.value = ''
  form.command = ''
  commandEdited.value = false
}
function changeMachine() {
  form.remote_file_id = null
  generatedCommand.value = ''
  if (form.mode === 'k8s' && !commandEdited.value) form.command = ''
}
function changeFile() {
  if (form.mode !== 'k8s') return
  const next = defaultK8sCommand(selectedFile.value?.path || '')
  if (!commandEdited.value || !form.command || form.command === generatedCommand.value) form.command = next
  generatedCommand.value = next
  commandEdited.value = false
}

async function loadOptions() {
  const { data } = await api.get<{ machines: CommandMachine[] }>('/command-executions/options/')
  machines.value = data.machines
}
async function loadExecutions(showLoading = true) {
  if (showLoading) loading.value = true
  try {
    const { data } = await api.get<PageResult<CommandExecution>>('/command-executions/', { params: { page: page.value, page_size: pageSize.value } })
    executions.value = data.results
    total.value = data.count
    if (selectedExecution.value) {
      const fresh = data.results.find(item => item.id === selectedExecution.value?.id)
      if (fresh) Object.assign(selectedExecution.value, fresh)
    }
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '加载执行历史失败') }
  finally { if (showLoading) loading.value = false }
}
async function refreshPage() {
  loading.value = true
  try { await Promise.all([loadOptions(), loadExecutions(false)]) }
  catch (error: any) { ElMessage.error(error.response?.data?.detail || '刷新命令执行页面失败') }
  finally { loading.value = false }
}
async function submit() {
  if (!form.file_config_id) return ElMessage.warning('请选择执行机器')
  if (form.mode === 'k8s' && !form.working_directory.trim()) return ElMessage.warning('K8s 模式必须填写执行路径')
  if (!form.command.trim()) return ElMessage.warning('请输入命令内容')
  submitting.value = true
  try {
    const { data } = await api.post<CommandExecution>('/command-executions/', form, { timeout: 15000 })
    data.outputs = []
    selectedExecution.value = data
    page.value = 1
    await loadExecutions(false)
    connectStream(data)
    ElMessage.success('命令已提交')
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '命令提交失败') }
  finally { submitting.value = false }
}
async function selectExecution(row: CommandExecution) {
  try {
    const { data } = await api.get<CommandExecution>(`/command-executions/${row.id}/`)
    selectedExecution.value = data
    if (terminalStatuses.includes(data.status)) disconnectStream(); else connectStream(data)
    await nextTick(scrollTerminal)
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '加载执行详情失败') }
}
async function stopExecution() {
  if (!selectedExecution.value) return
  stopping.value = true
  try {
    await api.post(`/command-executions/${selectedExecution.value.id}/stop/`)
    selectedExecution.value.stop_requested = true
    ElMessage.success('已发送停止请求')
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '停止命令失败') }
  finally { stopping.value = false }
}
function scrollTerminal() { if (terminalRef.value) terminalRef.value.scrollTop = terminalRef.value.scrollHeight }
watch(() => selectedExecution.value?.outputs?.length, () => void nextTick(scrollTerminal))
onMounted(() => { void refreshPage(); clockTimer = setInterval(() => { clock.value = Date.now() }, 1000) })
onUnmounted(() => { if (clockTimer) clearInterval(clockTimer) })
</script>

<style scoped>
.command-workbench { padding: 18px 20px 20px; border: 1px solid #e5e9ef; border-radius: 5px; background: #fff; }
.command-form-heading, .command-section-heading > div { display: flex; align-items: baseline; gap: 10px; }
.command-form-heading strong, .command-section-heading strong { color: #343b46; font-size: 15px; }
.command-form-heading span, .command-section-heading span { color: #99a2ae; font-size: 12px; }
.command-form { display: grid; grid-template-columns: 150px minmax(260px, 1.3fr) minmax(180px, .7fr) minmax(250px, 1fr); gap: 0 16px; margin-top: 15px; }
.command-form :deep(.el-form-item) { min-width: 0; margin-bottom: 16px; }
.command-form :deep(.el-form-item__label) { color: #616d7c; font-size: 13px; }
.command-form :deep(.el-select), .command-form :deep(.el-segmented) { width: 100%; }
.command-content-field { grid-column: 1 / -1; }
.command-content-field :deep(.el-textarea__inner) { font-family: Consolas, "Cascadia Code", monospace; font-size: 13px; line-height: 1.6; }
.command-submit-row { grid-column: 1 / -1; display: flex; align-items: center; justify-content: flex-end; gap: 16px; }
.command-submit-row span { min-width: 0; overflow: hidden; color: #8993a1; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.terminal-panel { margin-top: 14px; overflow: hidden; border-radius: 5px; background: #151a22; box-shadow: 0 8px 22px rgb(20 28 38 / 12%); }
.terminal-toolbar { display: flex; min-height: 47px; align-items: center; justify-content: space-between; gap: 12px; padding: 0 15px; border-bottom: 1px solid #2a303b; color: #d5dae2; background: #202630; }
.terminal-title, .terminal-meta { display: flex; min-width: 0; align-items: center; gap: 10px; }
.terminal-title strong { font-size: 13px; }
.terminal-title small { overflow: hidden; color: #8792a2; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.terminal-lights { display: flex; gap: 5px; }
.terminal-lights i { width: 8px; height: 8px; border-radius: 50%; background: #ef6461; }
.terminal-lights i:nth-child(2) { background: #e9b949; }
.terminal-lights i:nth-child(3) { background: #46b979; }
.terminal-meta { color: #9ba5b3; font-size: 12px; white-space: nowrap; }
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
.command-history { margin-top: 18px; }
.command-section-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.table-subtext { display: block; margin-top: 3px; color: #929ba7; font-size: 12px; }
.command-pagination { display: flex; justify-content: flex-end; padding-top: 16px; }
@media (max-width: 1100px) { .command-form { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 700px) { .command-form { grid-template-columns: 1fr; } .command-content-field, .command-submit-row { grid-column: 1; } .terminal-toolbar { align-items: flex-start; flex-direction: column; padding-block: 10px; } .terminal-meta { flex-wrap: wrap; } }
</style>
