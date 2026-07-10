<template>
  <el-drawer
    v-model="visible"
    class="report-drawer"
    direction="rtl"
    size="var(--panel-width)"
    @opened="handleDrawerOpened"
    @close="handleDrawerClose"
    @closed="handleDrawerClosed"
  >
    <template #header>
      <div class="drawer-heading">
        <div class="drawer-heading__icon" aria-hidden="true">
          <el-icon><DocumentChecked /></el-icon>
        </div>
        <div>
          <p class="technical-label">RESUME INTELLIGENCE</p>
          <h2>简历分析报告</h2>
        </div>
      </div>
    </template>

    <section class="report-panel" aria-label="简历分析报告">
      <div v-if="!reportText" class="report-state" role="status">
        <el-icon aria-hidden="true"><Document /></el-icon>
        <h3>暂无分析结果</h3>
        <p>上传简历后，向职达 AI 发起“分析简历”即可在这里查看结果。</p>
      </div>

      <template v-else>
        <section v-if="hasScore" class="score-overview" aria-labelledby="resume-score-title">
          <div class="score-chart-wrap">
            <div
              ref="chartRef"
              class="score-chart"
              role="img"
              :aria-label="`简历综合评分：${displayScore} 分（满分 10 分）`"
            ></div>
          </div>
          <div class="score-copy">
            <p class="technical-label">CURRENT RESUME SIGNAL</p>
            <h3 id="resume-score-title">综合评分</h3>
            <strong class="score-value tabular-nums">{{ displayScore }}<small>/10</small></strong>
            <p>评分来自本次分析结果；详细依据请见下方报告。</p>
          </div>
        </section>

        <section v-else class="score-unavailable" aria-labelledby="resume-score-unavailable-title">
          <el-icon aria-hidden="true"><WarningFilled /></el-icon>
          <div>
            <p class="technical-label">SCORE UNAVAILABLE</p>
            <h3 id="resume-score-unavailable-title">未解析到综合评分</h3>
            <p>报告正文仍可查看；系统不会用默认分数替代实际结果。</p>
          </div>
        </section>

        <section class="report-content" aria-labelledby="resume-report-content-title">
          <div class="report-content__heading">
            <div>
              <p class="technical-label">ANALYSIS DETAILS</p>
              <h3 id="resume-report-content-title">完整分析</h3>
            </div>
          </div>
          <div class="report-markdown" v-html="renderedReport"></div>
        </section>
      </template>
    </section>
  </el-drawer>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Document, DocumentChecked, WarningFilled } from '@element-plus/icons-vue'
import DOMPurify from 'dompurify'
import { GaugeChart } from 'echarts/charts'
import { init as initECharts, use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { marked } from 'marked'
import { useReducedMotion } from '../composables/useReducedMotion'

use([GaugeChart, CanvasRenderer])

const props = defineProps({
  reportText: { type: String, default: '' }
})

const visible = ref(false)
const drawerOpened = ref(false)
const chartRef = ref(null)
const { prefersReducedMotion } = useReducedMotion()
let scoreChart = null
let chartResizeObserver = null
let resizeFrame = null

const score = computed(() => {
  const primaryMatch = props.reportText.match(/(?:综合评分|评分)[^\n：:]*[：:]\s*(\d+(?:\.\d+)?)\s*分/i)
  const fallbackMatch = props.reportText.match(/(\d+(?:\.\d+)?)\s*分/)
  const rawScore = Number(primaryMatch?.[1] || fallbackMatch?.[1])

  return Number.isFinite(rawScore) && rawScore >= 0 && rawScore <= 10 ? rawScore : null
})

const hasScore = computed(() => score.value !== null)
const displayScore = computed(() => (
  Number.isInteger(score.value) ? score.value : score.value?.toFixed(1)
))
const scorePercent = computed(() => (score.value || 0) * 10)

const renderedReport = computed(() => (
  props.reportText ? DOMPurify.sanitize(marked(props.reportText)) : ''
))

const getToken = (name) => window
  .getComputedStyle(document.documentElement)
  .getPropertyValue(name)
  .trim()

const cancelScheduledResize = () => {
  if (resizeFrame === null) return
  cancelAnimationFrame(resizeFrame)
  resizeFrame = null
}

const disconnectChartObserver = () => {
  chartResizeObserver?.disconnect()
  chartResizeObserver = null
}

const disposeChart = () => {
  cancelScheduledResize()
  disconnectChartObserver()
  if (scoreChart) {
    scoreChart.dispose()
    scoreChart = null
  }
}

const scheduleChartResize = () => {
  if (!scoreChart || resizeFrame !== null) return

  resizeFrame = requestAnimationFrame(() => {
    resizeFrame = null
    scoreChart?.resize()
  })
}

const observeChartSize = () => {
  if (!chartRef.value || typeof ResizeObserver === 'undefined') return

  chartResizeObserver = new ResizeObserver(scheduleChartResize)
  chartResizeObserver.observe(chartRef.value)
}

const initChart = async () => {
  await nextTick()
  if (!visible.value || !drawerOpened.value || !hasScore.value || !chartRef.value) {
    disposeChart()
    return
  }

  disposeChart()
  scoreChart = initECharts(chartRef.value)
  scoreChart.setOption({
    animation: !prefersReducedMotion.value,
    animationDuration: prefersReducedMotion.value ? 0 : 240,
    animationDurationUpdate: prefersReducedMotion.value ? 0 : 180,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicOut',
    series: [{
      type: 'gauge',
      startAngle: 205,
      endAngle: -25,
      min: 0,
      max: 100,
      splitNumber: 5,
      pointer: { show: false },
      progress: {
        show: true,
        roundCap: true,
        width: 10,
        itemStyle: { color: getToken('--color-primary') }
      },
      axisLine: {
        roundCap: true,
        lineStyle: {
          width: 10,
          color: [[1, getToken('--color-surface-hover')]]
        }
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      anchor: { show: false },
      title: { show: false },
      detail: { show: false },
      data: [{ value: scorePercent.value }]
    }]
  })
  observeChartSize()
}

const handleDrawerOpened = () => {
  drawerOpened.value = true
  initChart()
}

const handleDrawerClose = () => {
  drawerOpened.value = false
}

const handleDrawerClosed = () => {
  drawerOpened.value = false
  disposeChart()
}

const open = () => {
  visible.value = true
}

const close = () => {
  visible.value = false
}

watch([() => props.reportText, prefersReducedMotion], () => {
  if (drawerOpened.value) initChart()
})

onBeforeUnmount(disposeChart)

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

.report-panel {
  display: grid;
  gap: var(--space-6);
  padding-bottom: var(--space-6);
}

.report-state,
.score-unavailable {
  display: grid;
  justify-items: center;
  padding: var(--space-10) var(--space-6);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-panel);
  background: var(--color-surface-subtle);
  color: var(--color-text-muted);
  text-align: center;
}

.report-state > .el-icon {
  margin-bottom: var(--space-4);
  color: var(--color-cyan);
  font-size: 2rem;
}

.report-state h3,
.score-unavailable h3 {
  margin-bottom: var(--space-2);
  font-size: var(--font-size-component-title);
}

.report-state p,
.score-unavailable p {
  max-width: 28rem;
  margin: 0;
  color: var(--color-text-secondary);
}

.score-overview {
  display: grid;
  grid-template-columns: minmax(9rem, .85fr) minmax(0, 1.15fr);
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-5);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-panel);
  background: var(--color-surface-subtle);
  box-shadow: var(--shadow-card);
}

.score-chart-wrap {
  min-width: 0;
}

.score-chart {
  width: 100%;
  min-width: 9rem;
  height: 9rem;
}

.score-copy .technical-label {
  margin: 0 0 var(--space-2);
}

.score-copy h3 {
  margin-bottom: var(--space-2);
  font-size: var(--font-size-component-title);
}

.score-value {
  display: block;
  margin-bottom: var(--space-3);
  color: var(--color-primary);
  font-size: var(--font-size-metric);
  line-height: 1;
}

.score-value small {
  margin-left: var(--space-1);
  color: var(--color-text-muted);
  font-size: var(--font-size-label);
  font-weight: 600;
}

.score-copy > p:last-child {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  line-height: var(--line-height-body);
}

.score-unavailable {
  grid-template-columns: auto minmax(0, 1fr);
  justify-items: start;
  gap: var(--space-3);
  padding: var(--space-5);
  border-style: solid;
  text-align: left;
}

.score-unavailable > .el-icon {
  margin-top: .15rem;
  color: var(--color-warning);
  font-size: 1.25rem;
}

.score-unavailable .technical-label {
  margin: 0 0 var(--space-1);
}

.report-content {
  padding-top: var(--space-6);
  border-top: 1px solid var(--color-border);
}

.report-content__heading {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}

.report-content__heading .technical-label {
  margin: 0 0 var(--space-1);
}

.report-content__heading h3 {
  margin: 0;
  font-size: var(--font-size-component-title);
}

.report-markdown {
  max-width: 70ch;
  overflow-wrap: anywhere;
  color: var(--color-text-secondary);
  font-size: var(--font-size-body);
  line-height: 1.85;
}

.report-markdown :deep(h1),
.report-markdown :deep(h2),
.report-markdown :deep(h3),
.report-markdown :deep(h4) {
  margin: var(--space-6) 0 var(--space-2);
  color: var(--color-text-primary);
  font-size: var(--font-size-component-title);
  line-height: var(--line-height-component-title);
}

.report-markdown :deep(h1:first-child),
.report-markdown :deep(h2:first-child),
.report-markdown :deep(h3:first-child),
.report-markdown :deep(h4:first-child),
.report-markdown :deep(p:first-child) {
  margin-top: 0;
}

.report-markdown :deep(p),
.report-markdown :deep(ul),
.report-markdown :deep(ol),
.report-markdown :deep(blockquote) {
  margin: 0 0 var(--space-3);
}

.report-markdown :deep(ul),
.report-markdown :deep(ol) {
  padding-left: var(--space-5);
}

.report-markdown :deep(li + li) {
  margin-top: var(--space-1);
}

.report-markdown :deep(strong) {
  color: var(--color-primary);
}

.report-markdown :deep(blockquote) {
  padding-left: var(--space-4);
  border-left: 2px solid var(--color-cyan);
  color: var(--color-text-secondary);
}

.report-markdown :deep(code) {
  padding: .12em .36em;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: .9em;
}

.report-markdown :deep(pre) {
  margin: var(--space-4) 0;
  padding: var(--space-4);
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
}

.report-markdown :deep(pre code) {
  padding: 0;
  border: 0;
  background: transparent;
}

@media (max-width: 440px) {
  .score-overview {
    grid-template-columns: 1fr;
  }

  .score-chart {
    width: min(100%, 12rem);
    margin: 0 auto;
  }
}
</style>
