<template>
  <button v-if="item" class="notification-ticker" type="button" title="查看文件配置" @click="$emit('open')">
    <span class="notification-ticker-viewport"><span class="notification-ticker-content">{{ item.message }}</span></span>
  </button>
</template>

<script setup lang="ts">
import type { ConfigNotification } from '../api'

defineProps<{ item: ConfigNotification | null }>()
defineEmits<{ open: [] }>()
</script>
