<template>
  <div ref="track" class="verify-track" :class="{ verified, dragging }">
    <span class="verify-caption" role="status" aria-live="polite">{{ message }}</span>
    <span v-if="challenge && !verified" class="verify-target" :style="{ left: targetPosition + 'px' }"></span>
    <button class="verify-handle" type="button" role="slider" aria-label="拖动滑块到目标位置，可使用方向键调整后按回车验证" :aria-valuemin="0" :aria-valuemax="320" :aria-valuenow="Math.round(position / travel * 320)" :style="{ transform: 'translateX(' + position + 'px)' }" :disabled="busy || verified || !challenge" @pointerdown="start" @pointermove="move" @pointerup="finish" @pointercancel="cancel" @keydown="keyboard">{{ verified ? '✓' : '›' }}</button>
    <button v-if="!challenge && !busy" type="button" class="verify-retry" @click="load">重试</button>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '../../api'

const props = defineProps<{ resetKey: number }>()
const emit = defineEmits<{ verified: [token: string] }>()
interface Challenge { challengeId: string; targetX: number; trackWidth: number; expiresIn: number }
const track = ref<HTMLElement | null>(null)
const challenge = ref<Challenge | null>(null)
const position = ref(0), travel = ref(280), busy = ref(false), verified = ref(false), dragging = ref(false)
const message = ref('加载滑块验证…')
const targetPosition = computed(() => challenge.value ? challenge.value.targetX / challenge.value.trackWidth * travel.value + 20 : 0)
let startedAt = 0, startX = 0, originalPosition = 0, generation = 0
let observer: ResizeObserver | undefined
let expiryTimer: ReturnType<typeof setTimeout> | undefined

async function load() {
  const current = ++generation
  clearTimeout(expiryTimer)
  emit('verified', '')
  verified.value = false
  dragging.value = false
  position.value = 0
  challenge.value = null
  busy.value = true
  message.value = '加载滑块验证…'
  try {
    const { data } = await api.get<Challenge>('/auth/slider-challenge/')
    if (current !== generation) return
    challenge.value = data
    message.value = '拖动滑块到目标位置'
    expiryTimer = setTimeout(load, data.expiresIn * 1000)
  } catch {
    if (current === generation) message.value = '验证加载失败'
  } finally { if (current === generation) busy.value = false }
}

function start(event: PointerEvent) {
  if (busy.value || verified.value || !challenge.value) return
  startedAt = performance.now()
  startX = event.clientX
  originalPosition = position.value
  dragging.value = true
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}

function move(event: PointerEvent) {
  if (dragging.value) position.value = Math.min(travel.value, Math.max(0, originalPosition + event.clientX - startX))
}

function cancel() { dragging.value = false; position.value = 0 }

async function verify() {
  if (!challenge.value || busy.value || verified.value) return
  const current = generation
  busy.value = true
  try {
    const { data } = await api.post<{ sliderToken: string }>('/auth/slider-verify/', { challengeId: challenge.value.challengeId, offsetX: position.value / travel.value * challenge.value.trackWidth, elapsedMs: Math.round(performance.now() - startedAt) })
    if (current !== generation) return
    verified.value = true
    message.value = '验证通过'
    emit('verified', data.sliderToken)
    clearTimeout(expiryTimer)
    expiryTimer = setTimeout(load, 120000)
  } catch (error: any) {
    if (current !== generation) return
    position.value = 0
    message.value = error.response?.data?.detail || '验证失败，请重新拖动'
  } finally { if (current === generation) busy.value = false }
}

function finish() { if (dragging.value) { dragging.value = false; void verify() } }
function keyboard(event: KeyboardEvent) {
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault()
    if (!startedAt) startedAt = performance.now()
    position.value = Math.max(0, Math.min(travel.value, position.value + (event.key === 'ArrowRight' ? 3 : -3)))
  } else if (event.key === 'Enter') { event.preventDefault(); void verify() }
}

watch(() => props.resetKey, load)
onMounted(() => {
  observer = new ResizeObserver(() => { travel.value = Math.max(1, (track.value?.clientWidth || 320) - 40); cancel() })
  if (track.value) observer.observe(track.value)
  void load()
})
onBeforeUnmount(() => { generation++; observer?.disconnect(); clearTimeout(expiryTimer) })
</script>

<style scoped>
.verify-track { position: relative; height: 44px; border: 1px solid var(--login-border, #d8dfee); border-radius: 12px; background: var(--login-input, #f9fbff); overflow: hidden; user-select: none; }
.verify-caption { position: absolute; inset: 0; display: grid; place-items: center; color: var(--login-muted, #64748b); font-size: 13px; }
.verify-target { position: absolute; top: 0; bottom: 0; width: 12px; margin-left: -6px; border-radius: 4px; border: 4px solid color-mix(in srgb, var(--login-accent, #953cff) 25%, white); background: var(--login-accent, #953cff); }
.verify-handle { position: absolute; left: 0; top: 0; height: 42px; width: 40px; padding: 0; border: 1px solid var(--login-border, #d8dfee); border-radius: 50%; color: var(--login-accent, #8a2eff); background: var(--login-surface, white); box-shadow: 0 2px 8px #53678422; cursor: grab; font-size: 26px; touch-action: none; }
.verify-handle:focus-visible { outline: 2px solid var(--login-accent, #953cff); outline-offset: -3px; }
.dragging .verify-handle { cursor: grabbing; }
.verified { border-color: #63bd96; }
.verified .verify-caption, .verified .verify-handle { color: #24815a; }
.verify-retry { position: absolute; right: 10px; top: 12px; border: 0; background: transparent; color: var(--login-accent, #953cff); cursor: pointer; }
</style>
