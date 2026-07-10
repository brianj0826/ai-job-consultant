<template>
  <section class="admin-page" data-testid="admin-overview-page">
    <div v-if="loading" class="admin-state" role="status">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在汇总平台数据…</span>
    </div>
    <div v-else-if="errorMessage" class="admin-state admin-state--error" role="alert">
      <el-icon><WarningFilled /></el-icon>
      <div><strong>概览加载失败</strong><p>{{ errorMessage }}</p></div>
      <el-button @click="load">重试</el-button>
    </div>
    <template v-else>
      <div class="admin-metric-grid">
        <article v-for="metric in metrics" :key="metric.label" class="admin-metric-card">
          <span>{{ metric.label }}</span>
          <strong class="tabular-nums">{{ metric.value }}</strong>
          <small>{{ metric.note }}</small>
        </article>
      </div>
      <section class="admin-panel">
        <div class="admin-panel__heading">
          <div><p class="technical-label">OPERATING SIGNALS</p><h2>今日运行信号</h2></div>
          <el-button @click="load">刷新</el-button>
        </div>
        <dl class="admin-signal-list">
          <div><dt>今日新增用户</dt><dd>{{ overview.users?.new_today || 0 }}</dd></div>
          <div><dt>今日登录用户</dt><dd>{{ overview.users?.logins_today || 0 }}</dd></div>
          <div><dt>有效认证会话</dt><dd>{{ overview.auth_sessions?.active || 0 }}</dd></div>
          <div><dt>已评价回复</dt><dd>{{ overview.feedback?.rated || 0 }}</dd></div>
        </dl>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Loading, WarningFilled } from '@element-plus/icons-vue'
import { getAdminOverview, getErrorMessage } from '../../api'

const overview = ref({})
const loading = ref(true)
const errorMessage = ref('')

const metrics = computed(() => [
  { label: '用户总数', value: overview.value.users?.total || 0, note: `${overview.value.users?.active || 0} 个活跃账号` },
  { label: '管理员', value: overview.value.users?.administrators || 0, note: '包含超级管理员' },
  { label: '会话总数', value: overview.value.conversations?.total || 0, note: '全平台职业对话' },
  { label: '消息总数', value: overview.value.messages?.total || 0, note: '用户与 AI 消息' },
  { label: '有帮助', value: overview.value.feedback?.likes || 0, note: `${overview.value.feedback?.dislikes || 0} 条需要改进` }
])

const load = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await getAdminOverview()
    overview.value = response.data
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '管理概览暂时不可用。')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
