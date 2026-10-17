<template>
  <div class="login-page">
    <div class="login-background"></div>
    <div class="login-card">
      <div class="login-brand"><span class="login-mark"><el-icon><Grid /></el-icon></span><strong>FileHub</strong></div>
      <div class="login-heading"><h1>欢迎回来</h1><p>登录运维控制台，管理您的服务器资源</p></div>
      <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="submit">
        <el-form-item prop="username"><el-input v-model="form.username" size="large" placeholder="用户名" :prefix-icon="UserIcon" /></el-form-item>
        <el-form-item prop="password"><el-input v-model="form.password" size="large" type="password" show-password placeholder="密码" :prefix-icon="Lock" /></el-form-item>
        <div class="login-options"><el-checkbox v-model="remember">记住登录状态</el-checkbox><a href="#" @click.prevent>忘记密码？</a></div>
        <el-button class="login-submit" type="primary" size="large" native-type="submit" :loading="loading">登录</el-button>
      </el-form>
      <div class="login-hint">开发环境默认管理员：<b>admin / admin123</b></div>
      <div class="login-footer">FileHub 运维控制台 · v1.0.0</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Grid, Lock, User as UserIcon } from '@element-plus/icons-vue'
import { login } from '../api'
import { authUser } from '../composables/useAuth'
import { landingPage } from '../features/access/model'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const remember = ref(true)
const form = reactive({ username: 'admin', password: 'admin123' })
const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
async function submit() {
  await formRef.value?.validate()
  loading.value = true
  try {
    const { user } = await login(form.username, form.password)
    authUser.value = user
    ElMessage.success('登录成功')
    router.push(landingPage(user))
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '登录失败，请检查账号密码')
  } finally {
    loading.value = false
  }
}
</script>
