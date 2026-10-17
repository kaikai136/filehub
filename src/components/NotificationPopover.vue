<template>
  <el-popover placement="bottom-end" :width="390" trigger="click" popper-class="notification-popper">
    <template #reference>
      <el-badge :value="unreadCount" :max="99" :hidden="unreadCount === 0" class="notification-badge">
        <button class="icon-button" type="button" aria-label="通知"><el-icon><Bell /></el-icon></button>
      </el-badge>
    </template>
    <div class="notification-panel">
      <div class="notification-panel-header">
        <strong>通知</strong>
        <el-button text type="primary" size="small" :disabled="unreadCount === 0" @click="$emit('read-all')">全部已读</el-button>
      </div>
      <div v-if="loading" class="notification-state"><el-icon class="is-loading"><Loading /></el-icon><span>正在加载</span></div>
      <div v-else-if="error" class="notification-state notification-error"><span>{{ error }}</span><el-button text type="primary" @click="$emit('refresh')">重试</el-button></div>
      <el-empty v-else-if="!items.length" :image-size="58" description="暂无配置变更" />
      <el-scrollbar v-else max-height="430px">
        <article v-for="item in items" :key="item.id" class="notification-item" :class="{ unread: !item.is_read }" @click="$emit('open', item)">
          <span v-if="!item.is_read" class="notification-unread-dot" aria-label="未读"></span>
          <div class="notification-item-body">
            <div class="notification-item-heading"><strong>{{ item.operator }}</strong><span>{{ notificationAction[item.event_type] }}了配置</span><time>{{ formatNotificationTime(item.occurred_at) }}</time></div>
            <div class="notification-machine">{{ notificationMachine(item) }}</div>
            <div class="notification-path" :title="item.path">{{ item.path || '未设置文件路径' }}</div>
          </div>
          <el-tooltip v-if="!item.is_read" content="标记已读" placement="left">
            <button class="notification-read" type="button" aria-label="标记已读" @click.stop="$emit('read', item)"><el-icon><CircleCheck /></el-icon></button>
          </el-tooltip>
        </article>
      </el-scrollbar>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { Bell, CircleCheck, Loading } from '@element-plus/icons-vue'
import type { ConfigNotification } from '../api'
import { formatNotificationTime, notificationAction, notificationMachine } from '../features/notifications/model'

defineProps<{ items: ConfigNotification[]; unreadCount: number; loading: boolean; error: string }>()
defineEmits<{
  open: [item: ConfigNotification]
  read: [item: ConfigNotification]
  'read-all': []
  refresh: []
}>()
</script>
