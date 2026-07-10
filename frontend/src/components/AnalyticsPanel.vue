<template>
  <el-drawer
    v-model="visible"
    class="analytics-drawer"
    direction="rtl"
    size="var(--panel-width)"
    @open="loadData"
  >
    <template #header>
      <div class="drawer-heading">
        <div class="drawer-heading__icon" aria-hidden="true">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <div>
          <p class="technical-label">CAREER INTELLIGENCE</p>
          <h2>数据分析</h2>
        </div>
      </div>
    </template>

    <section class="analytics-panel" aria-label="求职数据分析">
      <div v-if="loading" class="panel-state" role="status">
        <el-icon class="panel-state__icon is-loading" aria-hidden="true"><Loading /></el-icon>
        <h3>正在加载工作数据</h3>
        <p>正在汇总对话、反馈和知识库信息。</p>
      </div>

      <div v-else-if="loadError" class="panel-state panel-state--error" role="alert">
        <el-icon class="panel-state__icon" aria-hidden="true"><WarningFilled /></el-icon>
        <h3>暂时无法加载数据</h3>
        <p>{{ loadError }}</p>
        <el-button plain @click="loadData">重新加载</el-button>
      </div>

      <template v-else>
        <section class="analytics-section" aria-labelledby="analytics-overview-title">
          <div class="section-heading">
            <div>
              <p class="technical-label">CONVERSATION ACTIVITY</p>
              <h3 id="analytics-overview-title">求职对话概览</h3>
            </div>
            <el-icon aria-hidden="true"><TrendCharts /></el-icon>
          </div>

          <div class="metric-grid">
            <article class="metric-card metric-card--primary">
              <el-icon class="metric-icon" aria-hidden="true"><ChatDotRound /></el-icon>
              <strong class="metric-value tabular-nums">{{ overview.total_sessions }}</strong>
              <span>会话数</span>
            </article>
            <article class="metric-card metric-card--info">
              <el-icon class="metric-icon" aria-hidden="true"><TrendCharts /></el-icon>
              <strong class="metric-value tabular-nums">{{ overview.total_messages }}</strong>
              <span>消息数</span>
            </article>
            <article class="metric-card metric-card--cyan">
              <el-icon class="metric-icon" aria-hidden="true"><Document /></el-icon>
              <strong class="metric-value tabular-nums">{{ resumeCount ?? '—' }}</strong>
              <span>已上传文件</span>
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
            <el-icon aria-hidden="true"><CircleCheckFilled /></el-icon>
          </div>

          <template v-if="feedback.total_rated > 0">
            <div class="feedback-summary">
              <span>满意度</span>
              <strong class="tabular-nums">{{ feedback.like_rate }}%</strong>
              <span>{{ feedback.total_rated }} 条已评价回复</span>
            </div>

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
          </template>

          <div v-else class="section-empty-state">
            <el-icon aria-hidden="true"><ChatDotRound /></el-icon>
            <p>还没有已提交的回答反馈。</p>
          </div>
        </section>

        <section class="analytics-section" aria-labelledby="trend-title">
          <div class="section-heading">
            <div>
              <p class="technical-label">SEVEN-DAY SIGNAL</p>
              <h3 id="trend-title">近 7 天消息趋势</h3>
            </div>
            <el-icon aria-hidden="true"><TrendCharts /></el-icon>
          </div>

          <div v-if="hasTrendData" class="trend-list">
            <div v-for="item in trend" :key="item.date" class="trend-row">
              <time :datetime="item.date">{{ formatDate(item.date) }}</time>
              <el-progress
                class="trend-row__progress"
                :percentage="trendPercentage(item.count)"
                :color="statusColors.primary"
                :show-text="false"
                :stroke-width="8"
              />
              <strong class="trend-row__value tabular-nums">{{ item.count }}</strong>
            </div>
          </div>

          <div v-else class="section-empty-state">
            <el-icon aria-hidden="true"><TrendCharts /></el-icon>
            <p>最近 7 天还没有可展示的消息数据。</p>
          </div>
        </section>
      </template>
    </section>
  </el-drawer>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  ChatDotRound,
  CircleCheckFilled,
  CircleCloseFilled,
  DataAnalysis,
  Document,
  Loading,
  TrendCharts,
  WarningFilled
} from '@element-plus/icons-vue'
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
      getAnalyticsOverview(props.userId),
      getAnalyticsFeedback(props.userId),
      getAnalyticsTrend(props.userId, 7)
    ])

    overview.value = overviewResponse.data
    feedback.value = feedbackResponse.data
    trend.value = trendResponse.data

    try {
      const documentResponse = await getDocStatus(props.userId)
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
.drawer-heading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.drawer-heading__icon {
  display: grid;
  width: 2.25rem;
  height: 2.25rem;
  place-items: center;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-control);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.drawer-heading .technical-label {
  margin: 0 0 var(--space-1);
}

.drawer-heading h2 {
  margin: 0;
  font-size: var(--font-size-component-title);
  line-height: var(--line-height-component-title);
}

.analytics-panel {
  display: grid;
  gap: var(--space-8);
  padding-bottom: var(--space-6);
}

.analytics-section {
  padding-bottom: var(--space-8);
  border-bottom: 1px solid var(--color-border);
}

.analytics-section:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  color: var(--color-text-muted);
}

.section-heading .technical-label {
  margin: 0 0 var(--space-1);
}

.section-heading h3 {
  margin: 0;
  font-size: var(--font-size-component-title);
  line-height: var(--line-height-component-title);
}

.section-heading > .el-icon {
  margin-top: var(--space-1);
  color: var(--color-cyan);
  font-size: 1.15rem;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.metric-card {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface-subtle);
}

.metric-icon {
  color: var(--color-text-muted);
  font-size: 1rem;
}

.metric-value {
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: 1.75rem;
  line-height: 1;
  text-overflow: ellipsis;
}

.metric-card span {
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}

.metric-card--primary .metric-icon {
  color: var(--color-primary);
}

.metric-card--info .metric-icon {
  color: var(--color-electric-blue);
}

.metric-card--cyan .metric-icon {
  color: var(--color-cyan);
}

.data-note {
  margin: var(--space-3) 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}

.feedback-summary {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-1) var(--space-3);
  align-items: baseline;
  margin-bottom: var(--space-5);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface-subtle);
}

.feedback-summary > span:first-child {
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
}

.feedback-summary strong {
  color: var(--color-success);
  font-size: var(--font-size-metric);
  line-height: 1;
}

.feedback-summary > span:last-child {
  grid-column: 1 / -1;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}

.feedback-metric + .feedback-metric {
  margin-top: var(--space-4);
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
  align-items: center;
  gap: var(--space-2);
}

.feedback-metric__label--positive .el-icon {
  color: var(--color-success);
}

.feedback-metric__label--negative .el-icon {
  color: var(--color-danger);
}

.section-empty-state,
.panel-state {
  display: grid;
  justify-items: center;
  padding: var(--space-8) var(--space-5);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-card);
  background: var(--color-surface-subtle);
  color: var(--color-text-muted);
  text-align: center;
}

.section-empty-state .el-icon {
  margin-bottom: var(--space-2);
  color: var(--color-cyan);
  font-size: 1.25rem;
}

.section-empty-state p {
  margin: 0;
  font-size: var(--font-size-label);
}

.trend-list {
  display: grid;
  gap: var(--space-3);
}

.trend-row {
  display: grid;
  grid-template-columns: 2.75rem minmax(0, 1fr) 2rem;
  gap: var(--space-3);
  align-items: center;
}

.trend-row time,
.trend-row__value {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
}

.trend-row__value {
  color: var(--color-text-secondary);
  text-align: right;
}

.panel-state {
  min-height: 17rem;
  align-content: center;
  border-style: solid;
}

.panel-state--error {
  border-color: var(--color-danger);
  background: var(--color-danger-soft);
}

.panel-state__icon {
  margin-bottom: var(--space-4);
  color: var(--color-cyan);
  font-size: 2rem;
}

.panel-state--error .panel-state__icon {
  color: var(--color-danger);
}

.panel-state h3 {
  margin-bottom: var(--space-2);
  font-size: var(--font-size-component-title);
}

.panel-state p {
  max-width: 26rem;
  margin: 0 0 var(--space-4);
  color: var(--color-text-secondary);
}

@media (max-width: 420px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .metric-card {
    grid-template-columns: auto 1fr auto;
    align-items: center;
  }

  .metric-card span {
    text-align: right;
  }
}
</style>
