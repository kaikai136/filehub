<template>
  <div class="lock-screen" role="dialog" aria-modal="true" aria-labelledby="lock-screen-title">
    <div class="lock-screen-panel">
      <el-avatar :size="60">{{ avatarText }}</el-avatar>
      <h1 id="lock-screen-title">屏幕已锁定</h1>
      <p>{{ user?.name || user?.username }}</p>
      <el-form @submit.prevent="unlock">
        <el-input v-model="password" type="password" show-password autofocus autocomplete="current-password" placeholder="请输入登录密码" :prefix-icon="Lock" @keyup.enter="unlock" />
        <el-button type="primary" native-type="submit" :loading="loading" :disabled="!password">解锁</el-button>
      </el-form>
      <button class="lock-screen-logout" type="button" @click="$emit('logout')">退出登录</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'
import { api, type User } from '../api'

const props = defineProps<{ user: User | null }>()
const emit = defineEmits<{ unlocked: []; logout: [] }>()
const password = ref('')
const loading = ref(false)
const avatarText = computed(() => (props.user?.name || props.user?.username || 'U').slice(0, 1).toUpperCase())

async function unlock() {
  if (!password.value || loading.value) return
  loading.value = true
  try {
    await api.post('/auth/unlock/', { password: password.value })
    password.value = ''
    emit('unlocked')
  } catch (error: any) {
    password.value = ''
    ElMessage.error(error.response?.data?.detail || '解锁失败，请重新输入密码')
  } finally {
    loading.value = false
  }
}
</script>
