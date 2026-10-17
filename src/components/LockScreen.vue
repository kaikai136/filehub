<template>
  <div
    class="lockscreen"
    :class="{ 'on-lock-login': showLogin }"
    role="dialog"
    aria-modal="true"
    aria-label="锁屏"
    tabindex="-1"
    @keyup="openLogin"
    @mousedown.stop
    @contextmenu.prevent
  >
    <template v-if="!showLogin">
      <div class="lock-box">
        <button class="lock-trigger" type="button" title="解锁屏幕" aria-label="解锁屏幕" @click="openLogin">
          <el-icon class="locked-icon"><Lock /></el-icon>
          <el-icon class="unlocked-icon"><Unlock /></el-icon>
        </button>
      </div>

      <div class="battery-display" aria-live="polite">
        <div class="battery-number">{{ battery.level }}%</div>
        <div class="battery-contrast">
          <div class="battery-circle"></div>
          <ul class="battery-bubbles" aria-hidden="true">
            <li v-for="bubble in bubbles" :key="bubble.id" :style="bubble.style"></li>
          </ul>
        </div>
        <div class="battery-status">
          <div>{{ batteryStatus }}</div>
          <div v-if="showDischargingTime">剩余可使用时间：{{ dischargingTime }}</div>
          <div v-if="showChargingTime">距离电池充满需要：{{ chargingTime }}</div>
        </div>
      </div>

      <div class="lock-local-time">
        <div class="lock-time">{{ hour }}:{{ minute }}</div>
        <div class="lock-date">{{ month }}月{{ day }}号，星期{{ week }}</div>
      </div>
      <div class="computer-status" aria-label="设备状态">
        <span class="network-status" :class="{ offline: !online }" :title="online ? '网络已连接' : '网络已断开'">
          <el-icon><Connection /></el-icon>
        </span>
        <el-icon title="设备电源"><Switch /></el-icon>
      </div>
    </template>

    <div v-else class="lock-login-box">
      <el-avatar :size="128"><el-icon><User /></el-icon></el-avatar>
      <div class="lock-username">{{ user?.username || '' }}</div>
      <el-input
        ref="passwordInput"
        v-model="password"
        class="lock-password"
        type="password"
        autofocus
        autocomplete="current-password"
        placeholder="请输入登录密码"
        @keyup.enter.stop="unlock"
      >
        <template #suffix>
          <button class="password-submit" type="button" aria-label="进入系统" :disabled="loading" @click="unlock">
            <el-icon :class="{ 'is-loading': loading }"><Loading v-if="loading" /><ArrowRight v-else /></el-icon>
          </button>
        </template>
      </el-input>
      <div v-if="errorMessage" class="lock-error">{{ errorMessage }}</div>
      <div class="lock-login-actions">
        <button type="button" @click="backToLock">返回</button>
        <button type="button" @click="$emit('logout')">重新登录</button>
        <button type="button" @click="unlock">进入系统</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ArrowRight, Connection, Loading, Lock, Switch, Unlock, User } from '@element-plus/icons-vue'
import { api, type User as AuthUser } from '../api'

interface BatteryManagerLike extends EventTarget {
  charging: boolean
  chargingTime: number
  dischargingTime: number
  level: number
}

defineProps<{ user: AuthUser | null }>()
const emit = defineEmits<{ unlocked: []; logout: [] }>()
const showLogin = ref(false)
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')
const passwordInput = ref<{ focus: () => void } | null>(null)
const online = ref(navigator.onLine)
const now = ref(new Date())
const battery = reactive({ charging: false, chargingTime: 0, dischargingTime: 0, level: 100 })
let clockTimer: ReturnType<typeof setInterval> | undefined
let batteryManager: BatteryManagerLike | undefined

const hour = computed(() => String(now.value.getHours()).padStart(2, '0'))
const minute = computed(() => String(now.value.getMinutes()).padStart(2, '0'))
const month = computed(() => now.value.getMonth() + 1)
const day = computed(() => now.value.getDate())
const week = computed(() => '日一二三四五六'.charAt(now.value.getDay()))
const batteryStatus = computed(() => battery.charging && battery.level >= 100 ? '已充满' : battery.charging ? '充电中' : '已断开电源')
const showDischargingTime = computed(() => Number.isFinite(battery.dischargingTime) && battery.dischargingTime > 0)
const showChargingTime = computed(() => Number.isFinite(battery.chargingTime) && battery.chargingTime > 0)
const formatDuration = (seconds: number) => `${Math.floor(seconds / 3600)}小时${Math.floor((seconds / 60) % 60)}分钟`
const dischargingTime = computed(() => formatDuration(battery.dischargingTime))
const chargingTime = computed(() => formatDuration(battery.chargingTime))
const bubbles = Array.from({ length: 15 }, (_, index) => ({
  id: index,
  style: {
    '--bubble-left': `${(index * 37) % 91 + 4}%`,
    '--bubble-size': `${8 + (index * 11) % 24}px`,
    '--bubble-delay': `${-((index * 0.47) % 4).toFixed(2)}s`,
    '--bubble-duration': `${2.6 + (index % 5) * 0.42}s`,
  },
}))

function syncOnline() { online.value = navigator.onLine }
function handleWindowKeyup() { if (!showLogin.value) openLogin() }
function syncBattery() {
  if (!batteryManager) return
  battery.charging = batteryManager.charging
  battery.chargingTime = batteryManager.chargingTime
  battery.dischargingTime = batteryManager.dischargingTime
  battery.level = Math.round(batteryManager.level * 100)
}
function openLogin() {
  showLogin.value = true
  nextTick(() => passwordInput.value?.focus())
}
function backToLock() {
  showLogin.value = false
  password.value = ''
  errorMessage.value = ''
}
async function unlock() {
  if (!password.value.trim() || loading.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    await api.post('/auth/unlock/', { password: password.value })
    backToLock()
    emit('unlocked')
  } catch (error: any) {
    password.value = ''
    errorMessage.value = error.response?.data?.detail || '解锁失败，请重新输入密码'
    nextTick(() => passwordInput.value?.focus())
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  clockTimer = setInterval(() => { now.value = new Date() }, 1000)
  window.addEventListener('online', syncOnline)
  window.addEventListener('offline', syncOnline)
  window.addEventListener('keyup', handleWindowKeyup)
  const getBattery = (navigator as Navigator & { getBattery?: () => Promise<BatteryManagerLike> }).getBattery
  if (getBattery) {
    try {
      batteryManager = await getBattery.call(navigator)
      syncBattery()
      for (const event of ['chargingchange', 'chargingtimechange', 'dischargingtimechange', 'levelchange']) batteryManager.addEventListener(event, syncBattery)
    } catch { /* Battery Status API is optional. */ }
  }
})

onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer)
  window.removeEventListener('online', syncOnline)
  window.removeEventListener('offline', syncOnline)
  window.removeEventListener('keyup', handleWindowKeyup)
  if (batteryManager) for (const event of ['chargingchange', 'chargingtimechange', 'dischargingtimechange', 'levelchange']) batteryManager.removeEventListener(event, syncBattery)
})
</script>
