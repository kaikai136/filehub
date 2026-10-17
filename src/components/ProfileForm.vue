<template>
  <el-form label-position="top" class="settings-form settings-profile-form" :disabled="disabled">
    <el-form-item label="登录名"><el-input v-model="model.username" disabled /></el-form-item>
    <el-form-item label="姓名" required><el-input v-model="model.name" maxlength="150" /></el-form-item>
    <el-form-item label="邮箱"><el-input v-model="model.email" maxlength="254" /></el-form-item>
    <div class="settings-form-divider"><span>修改密码</span><small>不修改密码时保持以下三项为空。</small></div>
    <el-form-item label="当前密码"><el-input v-model="model.current_password" type="password" show-password autocomplete="current-password" /></el-form-item>
    <el-form-item label="新密码"><el-input v-model="model.new_password" type="password" show-password autocomplete="new-password" /></el-form-item>
    <el-form-item label="确认新密码"><el-input v-model="model.confirm_password" type="password" show-password autocomplete="new-password" /></el-form-item>
  </el-form>
</template>

<script setup lang="ts">
import type { ProfileFormValue } from '../features/profile/model'

defineProps<{ disabled?: boolean }>()
const model = defineModel<ProfileFormValue>({ required: true })
</script>
