<template>
  <section class="admin-page overview-page" data-testid="admin-overview-page">
    <div v-if="loading" class="admin-state overview-state" role="status">
      <span class="overview-state__glyph" aria-hidden="true">
        <el-icon class="is-loading"><Loading /></el-icon>
      </span>
      <span>
        <strong>正在汇总平台数据</strong>
        <small>连接管理控制平面…</small>
      </span>
    </div>
    <div v-else-if="errorMessage" class="admin-state admin-state--error overview-state overview-state--error" role="alert">
      <span class="overview-state__glyph" aria-hidden="true">
        <el-icon><WarningFilled /></el-icon>
      </span>
      <div class="overview-state__copy">
        <strong>概览加载失败</strong>
        <p>{{ errorMessage }}</p>
      </div>
      <el-button @click="load">重新连接</el-button>
    </div>
    <template v-else>
      <header class="overview-hero">
        <div>
          <p class="technical-label">CONTROL PLANE · LIVE METRICS</p>
          <h2>平台运行态势</h2>
          <p>账户、会话与质量反馈的当前数据快照。</p>
        </div>
        <span class="overview-live-marker">
          <i aria-hidden="true"></i>
          当前快照
        </span>
      </header>

      <div class="admin-metric-grid overview-metric-grid" role="list" aria-label="平台核心指标">
        <article v-for="metric in metrics" :key="metric.label" class="admin-metric-card" role="listitem">
          <div class="overview-metric-card__top">
            <span>{{ metric.label }}</span>
            <i aria-hidden="true"></i>
          </div>
          <strong class="tabular-nums">{{ metric.value }}</strong>
          <small>{{ metric.note }}</small>
        </article>
      </div>

      <section class="admin-panel overview-signals" aria-labelledby="operating-signals-title">
        <div class="admin-panel__heading">
          <div>
            <p class="technical-label">OPERATING SIGNALS · TODAY</p>
            <h2 id="operating-signals-title">今日运行信号</h2>
            <p class="overview-signals__summary">用于快速判断账户访问与反馈闭环是否正常。</p>
          </div>
          <el-button class="overview-refresh" @click="load">刷新数据</el-button>
        </div>
        <dl class="admin-signal-list">
          <div><dt><i aria-hidden="true"></i>今日新增用户</dt><dd class="tabular-nums">{{ overview.users?.new_today || 0 }}</dd></div>
          <div><dt><i aria-hidden="true"></i>今日登录用户</dt><dd class="tabular-nums">{{ overview.users?.logins_today || 0 }}</dd></div>
          <div><dt><i aria-hidden="true"></i>有效认证会话</dt><dd class="tabular-nums">{{ overview.auth_sessions?.active || 0 }}</dd></div>
          <div><dt><i aria-hidden="true"></i>已评价回复</dt><dd class="tabular-nums">{{ overview.feedback?.rated || 0 }}</dd></div>
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

<style scoped>
.overview-page {
  position: relative;
  overflow: clip;
  isolation: isolate;
}

.overview-page::before {
  position: absolute;
  z-index: -1;
  top: -7rem;
  right: -5rem;
  width: 25rem;
  height: 25rem;
  border: 1px solid var(--color-orbit);
  border-radius: 50%;
  background: radial-gradient(circle, var(--color-aurora-violet-soft) 0, transparent 66%);
  content: '';
  pointer-events: none;
}

.overview-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-6);
  margin-bottom: var(--space-6);
  padding: var(--space-2) 0;
}

.overview-hero h2 {
  margin: var(--space-2) 0 var(--space-2);
  font-size: clamp(1.65rem, 3vw, 2.5rem);
  line-height: 1.15;
  letter-spacing: -.035em;
}

.overview-hero > div > p:last-child,
.overview-signals__summary {
  margin: 0;
  color: var(--color-text-muted);
}

.overview-live-marker {
  display: inline-flex;
  min-height: var(--control-height-large);
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: var(--color-surface-glass);
  color: var(--color-text-secondary);
  box-shadow: var(--shadow-card);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  white-space: nowrap;
}

.overview-live-marker i {
  width: .5rem;
  height: .5rem;
  border-radius: 50%;
  background: var(--color-success);
  box-shadow: 0 0 0 .25rem var(--color-success-soft);
}

.overview-metric-grid {
  gap: var(--space-3);
}

.overview-metric-grid .admin-metric-card {
  position: relative;
  min-height: 10.5rem;
  align-content: space-between;
  overflow: hidden;
  border-color: var(--color-border);
  background:
    linear-gradient(155deg, var(--color-surface-elevated), var(--color-surface-subtle));
  box-shadow: none;
}

.overview-metric-grid .admin-metric-card::after {
  position: absolute;
  right: -2rem;
  bottom: -3rem;
  left: auto;
  width: 7rem;
  height: 7rem;
  border: 1px solid var(--color-orbit);
  border-radius: 50%;
  background: var(--aurora-gradient-soft);
  content: '';
  opacity: .56;
  pointer-events: none;
  transform: none;
  transition: none;
}

.overview-metric-grid .admin-metric-card:nth-child(2n)::after {
  right: -3.5rem;
  bottom: -1.75rem;
}

.overview-metric-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.overview-metric-card__top > span {
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  font-weight: 650;
}

.overview-metric-card__top i {
  width: .55rem;
  height: .55rem;
  border: 1px solid var(--color-primary);
  border-radius: 50%;
  box-shadow: 0 0 0 .25rem var(--color-primary-soft);
}

.overview-metric-grid .admin-metric-card strong {
  position: relative;
  z-index: 1;
  font-size: clamp(2rem, 3vw, 2.75rem);
  line-height: 1;
  letter-spacing: -.045em;
}

.overview-metric-grid .admin-metric-card small {
  position: relative;
  z-index: 1;
  color: var(--color-text-muted);
  line-height: 1.45;
}

.overview-signals {
  position: relative;
  overflow: hidden;
  padding: clamp(1.25rem, 3vw, 2rem);
  border-radius: var(--radius-panel);
  background:
    linear-gradient(135deg, var(--color-surface), var(--color-surface-subtle));
}

.overview-signals::before {
  position: absolute;
  top: 0;
  left: 0;
  width: 9rem;
  height: 1px;
  background: var(--aurora-gradient);
  content: '';
}

.overview-signals .admin-panel__heading {
  position: relative;
  z-index: 1;
  align-items: flex-end;
  margin-bottom: var(--space-6);
}

.overview-signals__summary {
  margin-top: var(--space-2);
  font-size: var(--font-size-caption);
}

.overview-refresh {
  min-width: 6.5rem;
}

.overview-page :deep(.el-button) {
  min-height: var(--control-height-large);
}

.overview-signals .admin-signal-list {
  position: relative;
  z-index: 1;
}

.overview-signals .admin-signal-list > div {
  position: relative;
  min-height: 7rem;
  padding: var(--space-4) var(--space-5);
  overflow: hidden;
  border: 1px solid var(--color-border);
  background: var(--color-surface-glass);
}

.overview-signals .admin-signal-list dt {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-secondary);
}

.overview-signals .admin-signal-list dt i {
  width: .35rem;
  height: .35rem;
  border-radius: 50%;
  background: var(--color-electric-blue);
}

.overview-signals .admin-signal-list dd {
  margin-top: var(--space-4);
  font-size: 1.75rem;
  letter-spacing: -.035em;
}

.overview-state {
  flex-wrap: wrap;
  padding: var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-panel);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.overview-state > span:last-child strong,
.overview-state > span:last-child small {
  display: block;
}

.overview-state > span:last-child small {
  margin-top: var(--space-1);
  color: var(--color-text-muted);
}

.overview-state__glyph {
  display: grid;
  width: 3rem;
  height: 3rem;
  place-items: center;
  border: 1px solid var(--color-orbit-strong);
  border-radius: 50%;
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.overview-state--error {
  justify-content: flex-start;
}

.overview-state__copy {
  min-width: min(18rem, 100%);
}

.overview-state--error :deep(.el-button) {
  margin-left: auto;
}

@media (max-width: 767px) {
  .overview-page::before {
    top: -4rem;
    right: -9rem;
  }

  .overview-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .overview-metric-grid .admin-metric-card {
    min-height: 8.5rem;
  }

  .overview-signals .admin-panel__heading {
    align-items: stretch;
    flex-direction: column;
  }

  .overview-refresh {
    width: 100%;
  }

  .overview-state {
    align-items: flex-start;
    justify-content: flex-start;
    padding: var(--space-5);
  }

  .overview-state--error :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .overview-state__glyph :deep(.is-loading) {
    animation-duration: 1.4s;
  }
}
</style>
