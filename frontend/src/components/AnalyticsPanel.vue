<template>
  <InsightDrawerShell v-model="visible" @open="loadData">
    <template #header="{ titleId, titleClass }">
      <div class="insight-heading">
        <span class="insight-heading__mark" aria-hidden="true">
          <i></i>
          <i></i>
          <i></i>
          <i></i>
        </span>
        <div>
          <h2 :id="titleId" :class="titleClass">数据分析</h2>
          <p class="technical-label">WORKSPACE INSIGHTS</p>
        </div>
      </div>
    </template>

    <section class="analytics-panel" aria-label="求职数据分析">
      <div v-if="loading" class="panel-state" role="status">
        <span class="panel-state__signal" aria-hidden="true">
          <el-icon class="panel-state__icon is-loading"><Loading /></el-icon>
        </span>
        <h3>正在加载工作数据</h3>
        <p>正在汇总对话、反馈和知识库信息。</p>
      </div>

      <div v-else-if="loadError" class="panel-state panel-state--error" role="alert">
        <span class="panel-state__signal" aria-hidden="true">
          <el-icon class="panel-state__icon"><WarningFilled /></el-icon>
        </span>
        <h3>暂时无法加载数据</h3>
        <p>{{ loadError }}</p>
        <el-button plain @click="loadData">
          <el-icon aria-hidden="true"><RefreshRight /></el-icon>
          重新加载
        </el-button>
      </div>

      <template v-else>
        <section class="analytics-section" aria-labelledby="analytics-overview-title">
          <div class="section-heading">
            <div>
              <p class="technical-label">CONVERSATION ACTIVITY</p>
              <h3 id="analytics-overview-title">求职对话概览</h3>
            </div>
          </div>

          <div class="metric-grid">
            <article class="metric-item">
              <span>会话数</span>
              <strong class="metric-value tabular-nums">{{ overview.total_sessions ?? '—' }}</strong>
            </article>
            <article class="metric-item">
              <span>消息数</span>
              <strong class="metric-value tabular-nums">{{ overview.total_messages ?? '—' }}</strong>
            </article>
            <article class="metric-item">
              <span>已上传文件</span>
              <strong class="metric-value tabular-nums">{{ resumeCount ?? '—' }}</strong>
            </article>
          </div>

          <p class="data-note">
            <span v-if="overview.total_sessions">平均每个会话 {{ overview.avg_per_session }} 条消息。</span>
            <span v-else>创建首个会话后，这里会显示真实的使用情况。</span>
          </p>
        </section>

        <section class="analytics-section" aria-labelledby="feedback-title">
          <div class="section-heading">
            <div>
              <p class="technical-label">RESPONSE QUALITY</p>
              <h3 id="feedback-title">反馈统计</h3>
            </div>
          </div>

          <template v-if="feedback.total_rated > 0">
            <div class="feedback-summary">
              <div>
                <span>满意度</span>
                <strong class="tabular-nums">{{ feedback.like_rate }}%</strong>
              </div>
              <p>{{ feedback.total_rated }} 条已评价回复</p>
            </div>

            <div class="feedback-breakdown">
              <div class="feedback-metric">
                <div class="feedback-metric__heading">
                  <span class="feedback-metric__label feedback-metric__label--positive">
                    <el-icon aria-hidden="true"><CircleCheckFilled /></el-icon>
                    有帮助
                  </span>
                  <strong class="tabular-nums">{{ feedback.likes }}</strong>
                </div>
                <el-progress
                  :percentage="feedback.like_rate"
                  :color="statusColors.success"
                  :show-text="false"
                  :stroke-width="8"
                />
              </div>

              <div class="feedback-metric">
                <div class="feedback-metric__heading">
                  <span class="feedback-metric__label feedback-metric__label--negative">
                    <el-icon aria-hidden="true"><CircleCloseFilled /></el-icon>
                    需要改进
                  </span>
                  <strong class="tabular-nums">{{ feedback.dislikes }}</strong>
                </div>
                <el-progress
                  :percentage="100 - feedback.like_rate"
                  :color="statusColors.danger"
                  :show-text="false"
                  :stroke-width="8"
                />
              </div>
            </div>
          </template>

          <div v-else class="section-empty-state">
            <span class="empty-illustration" aria-hidden="true">
              <el-icon><ChatDotRound /></el-icon>
              <i>—</i>
            </span>
            <h4>还没有已提交的回答反馈。</h4>
            <p>为 AI 回答标记有帮助或需要改进后，统计会显示在这里。</p>
          </div>
        </section>

        <section class="analytics-section" aria-labelledby="trend-title">
          <div class="section-heading">
            <div>
              <p class="technical-label">SEVEN-DAY SIGNAL</p>
              <h3 id="trend-title">近 7 天消息趋势</h3>
            </div>
          </div>

          <div
            class="trend-chart"
            :class="{ 'trend-chart--empty': !hasTrendData }"
            role="img"
            :aria-label="hasTrendData ? '近 7 天每日消息数量柱状图' : '近 7 天没有消息数据'"
          >
            <div class="trend-chart__grid" aria-hidden="true">
              <i></i><i></i><i></i><i></i>
            </div>
            <div v-if="hasTrendData" class="trend-bars" aria-hidden="true">
              <div v-for="item in trend" :key="item.date" class="trend-column">
                <strong class="tabular-nums">{{ item.count }}</strong>
                <span
                  class="trend-column__bar"
                  :style="{ '--trend-height': `${trendPercentage(item.count)}%` }"
                ></span>
                <time :datetime="item.date">{{ formatDate(item.date) }}</time>
              </div>
            </div>
          </div>

          <p v-if="!hasTrendData" class="trend-empty-note">最近 7 天还没有可展示的消息数据。</p>
        </section>

        <footer class="analytics-actions">
          <el-button plain @click="loadData">
            <el-icon aria-hidden="true"><RefreshRight /></el-icon>
            刷新数据
          </el-button>
        </footer>
      </template>
    </section>
  </InsightDrawerShell>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  ChatDotRound,
  CircleCheckFilled,
  CircleCloseFilled,
  Loading,
  RefreshRight,
  WarningFilled
} from '@element-plus/icons-vue'
import InsightDrawerShell from './InsightDrawerShell.vue'
import {
  getDocStatus,
  getAnalyticsFeedback,
  getAnalyticsOverview,
  getAnalyticsTrend
} from '../api'

const props = defineProps({
  userId: Number
})

const visible = ref(false)
const loading = ref(false)
const loadError = ref('')
const overview = ref({ total_sessions: 0, total_messages: 0, avg_per_session: 0 })
const feedback = ref({ likes: 0, dislikes: 0, no_feedback: 0, total_rated: 0, like_rate: 0 })
const trend = ref([])
const resumeCount = ref(null)

const statusColors = {
  success: 'var(--color-success)',
  danger: 'var(--color-danger)',
  primary: 'var(--color-primary)'
}

const maxTrendCount = computed(() => Math.max(...trend.value.map((item) => item.count), 1))
const hasTrendData = computed(() => trend.value.some((item) => item.count > 0))

const trendPercentage = (count) => Math.round((count / maxTrendCount.value) * 100)

const formatDate = (dateString) => {
  if (!dateString) return '—'
  const parts = dateString.split('-')
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : dateString
}

const loadData = async () => {
  if (!props.userId) {
    loadError.value = '当前用户信息不可用，请重新登录后再试。'
    return
  }

  loading.value = true
  loadError.value = ''

  try {
    const [overviewResponse, feedbackResponse, trendResponse] = await Promise.all([
      getAnalyticsOverview(),
      getAnalyticsFeedback(),
      getAnalyticsTrend(7)
    ])

    overview.value = overviewResponse.data
    feedback.value = feedbackResponse.data
    trend.value = trendResponse.data

    try {
      const documentResponse = await getDocStatus()
      resumeCount.value = (documentResponse.data.sources || [])
        .filter((source) => source.type === 'file')
        .length
    } catch {
      resumeCount.value = null
    }
  } catch (error) {
    loadError.value = error?.response?.data?.detail || '服务暂时不可用，请稍后重试。'
  } finally {
    loading.value = false
  }
}

const open = () => {
  visible.value = true
}

const close = () => {
  visible.value = false
}

defineExpose({ open, close })
</script>

<style scoped>
.insight-heading {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-4);
}

.insight-heading__mark {
  display: flex;
  height: 2rem;
  flex: 0 0 2.25rem;
  align-items: flex-end;
  justify-content: center;
  gap: .2rem;
  filter: drop-shadow(0 0 10px var(--color-aurora-violet-soft));
}

.insight-heading__mark i {
  width: .28rem;
  border-radius: var(--radius-pill);
  background: var(--aurora-gradient);
}

.insight-heading__mark i:nth-child(1) { height: 48%; }
.insight-heading__mark i:nth-child(2) { height: 92%; }
.insight-heading__mark i:nth-child(3) { height: 66%; }
.insight-heading__mark i:nth-child(4) { height: 38%; }

.insight-heading h2 {
  margin: 0 0 .1rem;
  color: var(--color-text-primary);
  font-size: 1.35rem;
  line-height: 1.6rem;
  letter-spacing: .03em;
}

.insight-heading .technical-label {
  margin: 0;
  color: var(--color-text-muted);
  font-size: .67rem;
  letter-spacing: .08em;
}

.analytics-panel {
  display: grid;
  min-width: 0;
}

.analytics-section {
  min-width: 0;
  padding: var(--space-6) 0 var(--space-8);
  border-bottom: 1px solid var(--color-border);
}

.analytics-section:first-of-type {
  padding-top: 0;
}

.section-heading {
  margin-bottom: var(--space-5);
}

.section-heading .technical-label {
  margin: 0 0 var(--space-2);
  color: var(--color-text-muted);
  font-size: .68rem;
  letter-spacing: .075em;
}

.section-heading h3 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 1.16rem;
  line-height: 1.55;
  letter-spacing: .025em;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 0 calc(var(--space-3) * -1);
}

.metric-item {
  display: grid;
  min-width: 0;
  justify-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-3);
  text-align: center;
}

.metric-item + .metric-item {
  border-left: 1px solid var(--color-border-strong);
}

.metric-item span {
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
  white-space: nowrap;
}

.metric-value {
  max-width: 100%;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: 1.5rem;
  font-weight: 560;
  line-height: 1;
  text-overflow: ellipsis;
}

.data-note {
  margin: var(--space-5) 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: 1.65;
}

.feedback-summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr);
  gap: var(--space-5);
  align-items: center;
  margin-bottom: var(--space-5);
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background:
    linear-gradient(135deg, var(--color-primary-soft), transparent 58%),
    var(--color-surface-subtle);
}

.feedback-summary > div {
  display: grid;
  gap: var(--space-1);
}

.feedback-summary span,
.feedback-summary p {
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}

.feedback-summary strong {
  color: var(--color-success);
  font-size: var(--font-size-metric);
  font-weight: 580;
  line-height: 1;
}

.feedback-summary p {
  margin: 0;
  line-height: 1.6;
}

.feedback-breakdown {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
}

.feedback-metric {
  min-width: 0;
}

.feedback-metric__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
}

.feedback-metric__label {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

.feedback-metric__label--positive .el-icon { color: var(--color-success); }
.feedback-metric__label--negative .el-icon { color: var(--color-danger); }

.feedback-metric :deep(.el-progress-bar__outer) {
  background: var(--color-surface-hover);
}

.section-empty-state,
.panel-state {
  display: grid;
  justify-items: center;
  text-align: center;
}

.section-empty-state {
  min-height: 10.5rem;
  align-content: center;
  padding: var(--space-5);
}

.empty-illustration {
  position: relative;
  display: grid;
  width: 5.25rem;
  height: 4.25rem;
  margin-bottom: var(--space-3);
  place-items: center;
  color: var(--color-text-muted);
}

.empty-illustration::before {
  position: absolute;
  width: 3rem;
  height: 3rem;
  border: 1px solid var(--color-border-strong);
  border-radius: 50%;
  background: var(--aurora-gradient-soft);
  content: '';
  opacity: .6;
}

.empty-illustration .el-icon {
  position: relative;
  z-index: 1;
  font-size: 3rem;
}

.empty-illustration i {
  position: absolute;
  right: .25rem;
  bottom: .3rem;
  z-index: 2;
  display: grid;
  width: 1.7rem;
  height: 1.7rem;
  place-items: center;
  border: 2px solid var(--color-primary);
  border-radius: 50%;
  background: var(--color-surface-elevated);
  color: var(--color-primary);
  font-family: var(--font-mono);
  font-style: normal;
  line-height: 1;
}

.section-empty-state h4 {
  margin: 0 0 var(--space-2);
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
  font-weight: 600;
}

.section-empty-state p {
  max-width: 25rem;
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: 1.65;
}

.trend-chart {
  position: relative;
  height: 11.5rem;
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-card);
  background:
    linear-gradient(180deg, var(--color-aurora-blue-soft), transparent 52%),
    var(--color-surface-subtle);
}

.trend-chart__grid {
  position: absolute;
  inset: var(--space-5) var(--space-4) 2.35rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.trend-chart__grid i {
  display: block;
  width: 100%;
  border-top: 1px dashed var(--color-border);
}

.trend-bars {
  position: absolute;
  inset: var(--space-4) var(--space-4) var(--space-3);
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: var(--space-2);
  align-items: end;
}

.trend-column {
  display: grid;
  height: 100%;
  min-width: 0;
  grid-template-rows: 1rem minmax(0, 1fr) 1rem;
  justify-items: center;
  align-items: end;
  gap: var(--space-1);
}

.trend-column strong,
.trend-column time {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: .62rem;
  line-height: 1;
}

.trend-column__bar {
  display: block;
  width: min(1.5rem, 72%);
  height: max(.2rem, var(--trend-height));
  max-height: 100%;
  border: 1px solid color-mix(in srgb, var(--color-cyan) 42%, transparent);
  border-radius: .3rem .3rem .1rem .1rem;
  background: var(--aurora-gradient);
  box-shadow: 0 0 1rem var(--color-aurora-violet-soft);
}

.trend-empty-note {
  margin: calc(var(--space-6) * -1) var(--space-4) 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: 1.6;
}

.panel-state {
  min-height: 23rem;
  align-content: center;
  padding: var(--space-8) var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface-subtle);
}

.panel-state--error {
  border-color: color-mix(in srgb, var(--color-danger) 45%, var(--color-border));
  background:
    radial-gradient(circle at 50% 30%, var(--color-danger-soft), transparent 45%),
    var(--color-surface-subtle);
}

.panel-state__signal {
  display: grid;
  width: 4rem;
  height: 4rem;
  margin-bottom: var(--space-4);
  place-items: center;
  border: 1px solid var(--color-border-strong);
  border-radius: 50%;
  background: var(--aurora-gradient-soft);
}

.panel-state__icon {
  color: var(--color-cyan);
  font-size: 1.65rem;
}

.panel-state--error .panel-state__icon { color: var(--color-danger); }

.panel-state h3 {
  margin: 0 0 var(--space-2);
  color: var(--color-text-primary);
  font-size: var(--font-size-component-title);
}

.panel-state p {
  max-width: 26rem;
  margin: 0 0 var(--space-5);
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.analytics-actions {
  padding-top: var(--space-6);
}

.analytics-actions .el-button,
.panel-state .el-button {
  min-height: 44px;
}

@media (max-width: 480px) {
  .analytics-section {
    padding-bottom: var(--space-6);
  }

  .metric-grid {
    margin-inline: calc(var(--space-2) * -1);
  }

  .metric-item {
    gap: var(--space-2);
    padding-inline: var(--space-2);
  }

  .metric-item span {
    font-size: .7rem;
  }

  .metric-value {
    font-size: 1.3rem;
  }

  .feedback-summary {
    grid-template-columns: 1fr;
  }

  .feedback-breakdown {
    grid-template-columns: 1fr;
  }

  .trend-chart {
    height: 10.5rem;
  }

  .trend-bars {
    gap: var(--space-1);
  }
}

@media (prefers-reduced-transparency: reduce) {
  .feedback-summary,
  .trend-chart,
  .panel-state--error {
    background: var(--color-surface-subtle);
  }
}
</style>
