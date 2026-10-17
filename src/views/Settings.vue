<template>
  <div class="page settings-page">
    <div class="page-heading">
      <div><div class="eyebrow">系统管理</div><h1>系统设置</h1><p>管理界面偏好、个人信息、水印和审计数据保留策略。</p></div>
      <el-button type="primary" :loading="saving" :icon="Check" @click="save">保存设置</el-button>
    </div>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />
    <el-skeleton v-if="loading" :rows="10" animated />
    <template v-else>
      <div class="settings-layout">
        <nav class="settings-nav" aria-label="设置分类">
          <button v-for="item in navItems" :key="item.key" :class="{ active: activeSection === item.key }" @click="activeSection = item.key"><el-icon><component :is="item.icon" /></el-icon>{{ item.label }}</button>
        </nav>
        <div class="settings-content">
          <section v-show="activeSection === 'interface'" class="settings-section">
            <div class="settings-section-heading"><div><h2>界面偏好</h2><p>调整 FileHub 控制台的基础显示方式。</p></div></div>
            <el-form label-position="top" class="settings-form">
              <el-form-item label="系统字体大小"><el-radio-group v-model="form.settings.font_size" :disabled="!canEditGlobal"><el-radio-button :value="14">小</el-radio-button><el-radio-button :value="16">标准</el-radio-button><el-radio-button :value="18">大</el-radio-button></el-radio-group><small>修改后立即应用到当前页面。</small></el-form-item>
            </el-form>
          </section>

          <section v-show="activeSection === 'profile'" class="settings-section">
            <div class="settings-section-heading"><div><h2>用户信息</h2><p>更新当前登录账号的显示信息和密码。</p></div></div>
            <ProfileForm v-model="form.user" :disabled="saving" />
          </section>

          <section v-show="activeSection === 'watermark'" class="settings-section">
            <div class="settings-section-heading"><div><h2>水印设置</h2><p>在控制台页面叠加轻量水印，便于区分操作环境。</p></div><el-switch v-model="form.settings.watermark_enabled" :disabled="!canEditGlobal" active-text="启用" inactive-text="关闭" /></div>
            <el-form label-position="top" class="settings-form">
              <el-form-item label="水印模式"><el-radio-group v-model="form.settings.watermark_mode" :disabled="!canEditGlobal"><el-radio-button value="username">登录用户名</el-radio-button><el-radio-button value="custom">自定义文字</el-radio-button></el-radio-group><small>用户名模式会根据当前登录账号分别显示。</small></el-form-item>
              <el-form-item v-if="form.settings.watermark_mode === 'custom'" label="自定义文字"><el-input v-model="form.settings.watermark_text" maxlength="120" :disabled="!canEditGlobal" placeholder="例如：FileHub 内部环境" /></el-form-item>
              <div class="settings-inline-fields"><el-form-item label="透明度"><el-slider v-model="form.settings.watermark_opacity" :min="5" :max="60" :disabled="!canEditGlobal" show-input /><small>{{ form.settings.watermark_opacity }}%</small></el-form-item><el-form-item label="倾斜角度"><el-slider v-model="form.settings.watermark_rotation" :min="-45" :max="45" :disabled="!canEditGlobal" show-input /><small>{{ form.settings.watermark_rotation }}°</small></el-form-item></div>
            </el-form>
            <div class="watermark-preview" :class="{ disabled: !form.settings.watermark_enabled }"><span v-for="item in 3" :key="item" :style="watermarkStyle">{{ watermarkPreviewText }}</span></div>
          </section>

          <section v-show="activeSection === 'retention'" class="settings-section">
            <div class="settings-section-heading"><div><h2>审计与操作日志</h2><p>设置审计数据的保留时长，超过期限的记录将在保存设置或访问审计页面时自动清理。</p></div></div>
            <el-form label-position="top" class="settings-form settings-retention-form">
              <el-form-item label="文件审计过期时间"><el-input-number v-model="form.settings.file_audit_retention_days" :min="1" :max="3650" :disabled="!canEditGlobal" controls-position="right" /><span class="field-suffix">天</span></el-form-item>
              <el-form-item label="操作日志过期时间"><el-input-number v-model="form.settings.operation_audit_retention_days" :min="1" :max="3650" :disabled="!canEditGlobal" controls-position="right" /><span class="field-suffix">天</span></el-form-item>
            </el-form>
            <el-alert v-if="!canEditGlobal" title="只有超级管理员可以修改全局界面、水印和日志保留设置。" type="info" :closable="false" />
          </section>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, Document, Edit, Monitor, User } from '@element-plus/icons-vue'
import ProfileForm from '../components/ProfileForm.vue'
import { api, type SettingsResponse, type SystemSettings } from '../api'
import { applySystemSettings } from '../composables/useSettings'
import { authUser } from '../composables/useAuth'
import { createProfileForm, profilePayload, validateProfile } from '../features/profile/model'

const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const activeSection = ref('interface')
const navItems = [{ key: 'interface', label: '界面偏好', icon: Monitor }, { key: 'profile', label: '用户信息', icon: User }, { key: 'watermark', label: '水印设置', icon: Edit }, { key: 'retention', label: '审计与日志', icon: Document }]
const emptySettings: SystemSettings = { font_size: 16, watermark_enabled: false, watermark_mode: 'username', watermark_text: 'FileHub', watermark_opacity: 12, watermark_rotation: -20, file_audit_retention_days: 180, operation_audit_retention_days: 180, can_edit_global: false, updated_at: '' }
const form = reactive({ settings: { ...emptySettings }, user: createProfileForm() })
const canEditGlobal = computed(() => form.settings.can_edit_global)
const watermarkStyle = computed(() => ({ opacity: form.settings.watermark_opacity / 100, transform: `rotate(${form.settings.watermark_rotation}deg)` }))
const watermarkPreviewText = computed(() => form.settings.watermark_mode === 'username' ? (form.user.username || 'username') : (form.settings.watermark_text || '自定义水印'))

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    const { data } = await api.get<SettingsResponse>('/settings/')
    Object.assign(form.settings, data.settings)
    Object.assign(form.user, createProfileForm(data.user))
    authUser.value = data.user
    applySystemSettings(data.settings)
  } catch (error: any) {
    errorMessage.value = error.response?.data?.detail || '加载系统设置失败'
  } finally { loading.value = false }
}

async function save() {
  if (saving.value) return
  const profileError = validateProfile(form.user)
  if (profileError) { ElMessage.error(profileError); activeSection.value = 'profile'; return }
  saving.value = true
  try {
    const payload = { settings: canEditGlobal.value ? { ...form.settings } : {}, user: profilePayload(form.user) }
    const { data } = await api.patch<SettingsResponse>('/settings/', payload)
    Object.assign(form.settings, data.settings)
    Object.assign(form.user, createProfileForm(data.user))
    authUser.value = data.user
    localStorage.setItem('confighub_user', JSON.stringify(data.user))
    applySystemSettings(data.settings)
    ElMessage.success('设置已保存')
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '保存设置失败') } finally { saving.value = false }
}

onMounted(load)
</script>
