<template>
  <main class="secure-login" :class="{ 'is-dark': appearance.dark, 'is-glass': appearance.layout === 'glass' }">
    <div class="login-particles" aria-hidden="true"><i v-for="particle in 18" :key="particle" :style="{ left: (particle * 37 % 100) + '%', top: (particle * 23 % 100) + '%', animationDelay: particle * -.4 + 's' }"></i></div>
    <nav class="login-controls" aria-label="登录页外观">
      <button type="button" @click="appearance.layout = appearance.layout === 'characters' ? 'glass' : 'characters'">{{ appearance.layout === 'characters' ? '动感玻璃' : '角色布局' }}</button>
      <button type="button" :aria-label="appearance.dark ? '切换明亮模式' : '切换暗黑模式'" @click="appearance.dark = !appearance.dark">{{ appearance.dark ? '☀ 明亮' : '☾ 暗黑' }}</button>
    </nav>
    <Transition name="welcome"><div v-if="welcomeVisible" class="login-welcome" role="status"><span class="welcome-emblem">F</span><h1>欢迎来到 FileHub</h1><p>您的安全运维工作空间</p></div></Transition>
    <section class="secure-login-card" aria-label="FileHub 登录">
      <div class="login-visual" aria-hidden="true">
        <div v-if="appearance.layout === 'glass'" class="glass-orbits"><span></span><span></span><span></span><strong>FileHub</strong><small>安全连接 · 高效运维</small></div>
        <LoginCharacters v-else :active="!welcomeVisible" :is-typing="isTyping" :show-password="showPassword" :password-length="password.length" />
        <span class="visual-caption">FileHub · Secure Workspace</span>
      </div>
      <div class="login-form-panel">
        <div class="secure-badge">● FileHub · Secure Console</div>
        <h1>{{ pendingSetup ? '绑定双因素认证' : pending ? '双因素认证' : '欢迎回来' }}</h1>
        <p class="login-description">{{ pendingSetup ? '请使用验证器扫描二维码，然后输入 6 位动态验证码完成绑定。' : pending ? '请输入验证器中的 6 位动态验证码。' : '登录管理平台，继续处理文件、主机和系统管理任务。' }}</p>
        <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />
        <el-alert v-else-if="route.query.expired" title="登录已过期，请重新登录" type="info" :closable="false" show-icon />
        <form v-if="!pending && !pendingSetup" class="secure-form" @submit.prevent="submit">
          <el-input v-model="username" size="large" placeholder="用户名" aria-label="用户名" autocomplete="username" :prefix-icon="UserIcon" :disabled="loading" @focus="isTyping = true" @blur="isTyping = false" />
          <el-input v-model="password" size="large" :type="showPassword ? 'text' : 'password'" placeholder="密码" aria-label="密码" autocomplete="current-password" :prefix-icon="Lock" :disabled="loading">
            <template #suffix><button class="password-toggle" type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" :aria-pressed="showPassword" @click="showPassword = !showPassword"><el-icon><Hide v-if="showPassword" /><View v-else /></el-icon></button></template>
          </el-input>
          <el-checkbox v-model="remember" :disabled="loading">记住我<span class="remember-note">（仅用户名）</span></el-checkbox>
          <LoginSlider :reset-key="sliderResetKey" @verified="sliderToken = $event" />
          <el-button class="secure-submit" type="primary" size="large" native-type="submit" :loading="loading" :disabled="!username.trim() || !password || !sliderToken">登　录</el-button>
        </form>
        <form v-else class="secure-form" @submit.prevent="pendingSetup ? submitTwoFactorSetup() : submitTwoFactor()">
          <div v-if="pendingSetup" class="setup-qr-wrap"><img :src="pendingSetup.qr_data_url" alt="双因素认证绑定二维码" /><code>{{ pendingSetup.secret }}</code><small>绑定挑战将在 {{ pendingSetup.expiresIn }} 秒后过期。</small></div>
          <el-input v-model="code" size="large" placeholder="6 位动态验证码" aria-label="动态验证码" inputmode="numeric" autocomplete="one-time-code" maxlength="6" :disabled="loading" />
          <el-button class="secure-submit" type="primary" size="large" native-type="submit" :loading="loading" :disabled="!/^[0-9]{6}$/.test(code)">{{ pendingSetup ? '绑定并登录' : '验证并登录' }}</el-button>
          <el-button text :disabled="loading" @click="cancelTwoFactor">返回账号登录</el-button>
        </form>
        <footer class="secure-login-footer">FileHub 运维控制台 · 安全访问</footer>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, User as UserIcon, Hide, View } from '@element-plus/icons-vue'
import { api, login, storeAuth, type LoginSuccess, type TwoFactorChallenge, type TwoFactorSetupChallenge } from '../api'
import { authUser } from '../composables/useAuth'
import { landingPage } from '../features/access/model'
import { normalizeAppearance, rememberedUsername, rememberUsername } from '../features/auth/model'
import LoginCharacters from '../components/login/LoginCharacters.vue'
import LoginSlider from '../components/login/LoginSlider.vue'

const router = useRouter(), route = useRoute()
const username = ref(rememberedUsername(localStorage)), password = ref(''), remember = ref(Boolean(username.value))
const showPassword = ref(false), isTyping = ref(false), loading = ref(false), errorMessage = ref('')
const sliderToken = ref(''), sliderResetKey = ref(0), code = ref('')
const pending = ref<TwoFactorChallenge | null>(null)
const pendingSetup = ref<TwoFactorSetupChallenge | null>(null)
let storedAppearance: unknown = null
try { storedAppearance = JSON.parse(localStorage.getItem('filehub_login_appearance') || 'null') } catch { storedAppearance = null }
const appearance = reactive(normalizeAppearance(storedAppearance))
watch(appearance, value => localStorage.setItem('filehub_login_appearance', JSON.stringify(value)))
const welcomeVisible = ref(!sessionStorage.getItem('filehub_login_welcomed'))
const welcomeTimer = setTimeout(() => { welcomeVisible.value = false; sessionStorage.setItem('filehub_login_welcomed', '1') }, 1100)
onBeforeUnmount(() => clearTimeout(welcomeTimer))

async function complete(data: LoginSuccess) {
  storeAuth(data)
  authUser.value = data.user
  rememberUsername(localStorage, username.value, remember.value)
  password.value = ''
  code.value = ''
  await router.replace(landingPage(data.user))
}

async function submit() {
  if (loading.value || !username.value.trim() || !password.value || !sliderToken.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await login(username.value.trim(), password.value, sliderToken.value)
    if ('twoFactorSetupRequired' in result) { pendingSetup.value = result; pending.value = null; code.value = '' }
    else if ('twoFactorRequired' in result) { pending.value = result; pendingSetup.value = null; code.value = '' }
    else await complete(result)
  } catch (error: any) { errorMessage.value = error.response?.data?.detail || '登录失败，请稍后重试' }
  finally { password.value = ''; showPassword.value = false; sliderToken.value = ''; sliderResetKey.value++; loading.value = false }
}

async function submitTwoFactor() {
  if (loading.value || !pending.value || !/^[0-9]{6}$/.test(code.value)) return
  loading.value = true
  errorMessage.value = ''
  try {
    const { data } = await api.post<LoginSuccess>('/auth/verify-two-factor/', { challenge: pending.value.challenge, code: code.value })
    await complete(data)
  } catch (error: any) {
    if (error.response?.data?.restart_login) cancelTwoFactor()
    errorMessage.value = error.response?.data?.detail || '验证失败，请稍后重试'
  } finally { code.value = ''; loading.value = false }
}

async function submitTwoFactorSetup() {
  if (loading.value || !pendingSetup.value || !/^[0-9]{6}$/.test(code.value)) return
  loading.value = true
  errorMessage.value = ''
  try {
    const { data } = await api.post<LoginSuccess>('/auth/verify-two-factor-setup/', { challenge: pendingSetup.value.challenge, code: code.value })
    await complete(data)
  } catch (error: any) {
    if (error.response?.data?.restart_login) cancelTwoFactor()
    errorMessage.value = error.response?.data?.detail || '绑定失败，请稍后重试'
  } finally { code.value = ''; loading.value = false }
}

function cancelTwoFactor() { pending.value = null; pendingSetup.value = null; password.value = ''; code.value = ''; sliderToken.value = ''; sliderResetKey.value++; errorMessage.value = '' }
</script>

<style scoped>
.secure-login { --login-surface: #ffffff; --login-input: #f9fbff; --login-border: #d6dfec; --login-text: #34256a; --login-muted: #697b96; --el-color-primary: #953cff; position: relative; display: grid; place-items: center; min-height: 100dvh; padding: 60px 24px; overflow: hidden; color: var(--login-text); background: radial-gradient(ellipse at 90% 30%, #ede5ff99, transparent 55%), #f3f6f9; }
.secure-login.is-dark { --login-surface: #211e35; --login-input: #28243d; --login-border: #49425f; --login-text: #efe8ff; --login-muted: #bbb1d2; background: radial-gradient(ellipse at 80% 30%, #56248666, transparent 60%), #151321; color-scheme: dark; }
.secure-login-card { z-index: 1; width: min(960px, 100%); min-height: 590px; display: grid; grid-template-columns: 45% 55%; overflow: hidden; border-radius: 24px; border: 1px solid #ffffff66; background: var(--login-surface); box-shadow: 0 28px 42px -22px #26314966; }
.login-visual { position: relative; overflow: hidden; min-height: 590px; background: linear-gradient(145deg, #a54aff, #6d0ed7 60%, #5c12b7); }
.visual-caption { position: absolute; bottom: 24px; left: 0; right: 0; text-align: center; font-size: 11px; letter-spacing: 1.5px; color: #ffffffaa; }
.login-form-panel { display: flex; flex-direction: column; justify-content: center; padding: 64px 15.8% 40px; text-align: center; background: radial-gradient(circle at 100% 100%, #b99aff13, transparent 70%); }
.secure-badge { align-self: center; white-space: nowrap; border: 1px solid #bc8cff55; border-radius: 24px; padding: 6px 13px; color: #963cff; background: #bb8bff13; font-size: 11px; font-weight: 650; letter-spacing: 1px; box-shadow: 0 3px 12px #953cff0f; }
.login-form-panel h1 { margin: 18px 0 10px; font-size: 30px; letter-spacing: -1px; color: var(--login-text); }
.login-description { margin: 0 0 30px; font-size: 12px; line-height: 1.7; color: var(--login-muted); font-weight: 550; }
.secure-form { display: grid; gap: 20px; margin-top: 4px; text-align: left; }
.setup-qr-wrap { display: grid; justify-items: center; gap: 10px; color: var(--login-muted); text-align: center; }
.setup-qr-wrap img { width: 190px; max-width: 100%; padding: 10px; border-radius: 10px; background: white; }
.setup-qr-wrap code { padding: 8px 10px; color: var(--login-text); background: var(--login-input); overflow-wrap: anywhere; user-select: all; }
.setup-qr-wrap small { font-size: 11px; }
.secure-form :deep(.el-input__wrapper) { height: 48px; padding: 0 15px; border-radius: 13px; background: var(--login-input); box-shadow: 0 0 0 1px var(--login-border) inset; }
.secure-form :deep(.el-input__inner) { color: var(--login-text); }
.secure-form :deep(.el-input__prefix), .secure-form :deep(.el-checkbox__label) { color: var(--login-muted); }
.secure-form :deep(.el-checkbox__inner) { background: var(--login-input); border-color: var(--login-border); border-radius: 5px; }
.secure-form :deep(.el-checkbox__input.is-checked .el-checkbox__inner) { background: #953cff; border-color: #953cff; }
.secure-form :deep(.el-checkbox) { height: 28px; }
.remember-note { color: var(--login-muted); opacity: .65; font-size: 11px; }
.password-toggle { display: grid; place-items: center; border: 0; padding: 4px; background: transparent; color: var(--login-muted); cursor: pointer; }
.secure-submit { width: 100%; height: 50px; border-radius: 13px; border: 0; background: #953cff; box-shadow: 0 8px 24px #953cff33; font-weight: 600; }
.secure-submit.is-disabled { background: #d9bbfa; color: white; opacity: .9; }
.secure-login-footer { margin-top: 28px; font-size: 10px; color: var(--login-muted); opacity: .6; }
.login-controls { position: absolute; z-index: 3; right: 24px; top: 18px; display: flex; gap: 8px; }
.login-controls button { padding: 7px 11px; border-radius: 18px; border: 1px solid var(--login-border); background: var(--login-surface); color: var(--login-muted); font-size: 12px; cursor: pointer; }
.login-particles { position: absolute; inset: 0; pointer-events: none; }
.login-particles i { position: absolute; width: 6px; height: 6px; border-radius: 50%; background: #b784ff55; animation: float 6s ease-in-out infinite; }
.is-glass .secure-login-card { border-color: #ffffff44; backdrop-filter: blur(24px); background: color-mix(in srgb, var(--login-surface) 75%, transparent); }
.is-glass .login-visual { background: linear-gradient(145deg, #603caa, #292455); }
.glass-orbits { position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white; }
.glass-orbits strong { font-size: 48px; z-index: 1; letter-spacing: -2px; }
.glass-orbits small { z-index: 1; margin-top: 12px; color: #ddd1ff; }
.glass-orbits span { position: absolute; width: 270px; height: 270px; border: 1px solid #cdb0ff66; border-radius: 40%; animation: orbit 16s linear infinite; box-shadow: 0 0 70px #b78fff22; }
.glass-orbits span:nth-child(2) { width: 330px; height: 330px; animation-direction: reverse; }
.glass-orbits span:nth-child(3) { width: 200px; height: 200px; background: #b798ff22; animation-duration: 10s; }
.login-welcome { position: fixed; z-index: 5; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; background: var(--login-surface); color: var(--login-text); pointer-events: none; }
.welcome-emblem { display: grid; place-items: center; width: 70px; height: 70px; border-radius: 22px; color: white; background: linear-gradient(135deg, #b264ff, #6d1be4); font-size: 40px; box-shadow: 0 12px 36px #953cff44; animation: enter .65s ease both; }
.login-welcome h1 { font-size: 26px; margin: 26px 0 6px; }
.login-welcome p { font-size: 13px; color: var(--login-muted); }
.welcome-leave-active { transition: opacity .4s, transform .4s; }
.welcome-leave-to { opacity: 0; transform: scale(1.03); }
@keyframes float { 50% { transform: translateY(-16px); } }
@keyframes orbit { to { transform: rotate(360deg); } }
@keyframes enter { from { opacity: 0; transform: translateY(15px) scale(.9); } }
@media (max-width: 760px) { .secure-login-card { max-width: 450px; grid-template-columns: 1fr; min-height: 570px; } .login-visual { display: none; } .login-form-panel { padding: 48px 32px 32px; } .secure-login { padding: 72px 16px 24px; } }
@media (prefers-reduced-motion: reduce) { .login-particles i, .glass-orbits span, .welcome-emblem { animation: none; } .welcome-leave-active { transition: none; } }
</style>
