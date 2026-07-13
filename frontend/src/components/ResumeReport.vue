<template>
  <InsightDrawerShell
    v-model="visible"
    @opened="handleDrawerOpened"
    @close="handleDrawerClose"
    @closed="handleDrawerClosed"
  >
    <template #header="{ titleId, titleClass }">
      <div class="drawer-heading">
        <div class="drawer-heading__icon" aria-hidden="true">
          <el-icon><DocumentChecked /></el-icon>
        </div>
        <div>
          <p class="technical-label">RESUME INTELLIGENCE</p>
          <h2 :id="titleId" :class="titleClass">简历分析报告</h2>
        </div>
      </div>
    </template>

    <section class="report-panel" aria-label="简历分析报告">
      <div v-if="!reportText" class="report-state" role="status">
        <div class="report-state__visual" aria-hidden="true">
          <span class="report-state__orbit"></span>
          <el-icon><Document /></el-icon>
        </div>
        <p class="technical-label">AWAITING ANALYSIS</p>
        <h3>暂无分析结果</h3>
        <p>上传简历后，向职达 AI 发起“分析简历”，真实分析结果会显示在这里。</p>
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
          <div class="score-unavailable__copy">
            <p class="technical-label">SCORE UNAVAILABLE</p>
            <h3 id="resume-score-unavailable-title">未解析到综合评分</h3>
            <p>报告正文仍可查看；系统不会用默认分数替代实际结果。</p>
          </div>
          <strong class="score-unavailable__value tabular-nums" aria-label="综合评分未解析">—</strong>
        </section>

        <section class="report-content" aria-labelledby="resume-report-content-title">
          <div class="report-content__heading">
            <div>
              <p class="technical-label">ANALYSIS DETAILS</p>
              <h3 id="resume-report-content-title">完整分析</h3>
            </div>
            <span class="report-content__status">基于本次报告</span>
          </div>
          <div class="report-markdown" v-html="renderedReport"></div>
        </section>
      </template>
    </section>
  </InsightDrawerShell>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Document, DocumentChecked, WarningFilled } from '@element-plus/icons-vue'
import { GaugeChart } from 'echarts/charts'
import { init as initECharts, use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { useReducedMotion } from '../composables/useReducedMotion'
import { renderAccessibleMarkdown } from '../utils/markdownAccessibility'
import InsightDrawerShell from './InsightDrawerShell.vue'

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
  const scoreLine = props.reportText
    .split('\n')
    .map((line) => line.replace(/[*_#`]/g, '').trim())
    .map((line) => line.match(
      /^(?:[-•]\s*)?(?:综合评分|评分)\s*(?:[：:]|\s)\s*(\d+(?:\.\d+)?)\s*(?:\/\s*10)?\s*(?:分)?\s*(?:[（(][^)）]*[)）])?\s*$/i
    ))
    .find(Boolean)
  const rawScore = Number(scoreLine?.[1])

  return Number.isFinite(rawScore) && rawScore >= 0 && rawScore <= 10 ? rawScore : null
})

const hasScore = computed(() => score.value !== null)
const displayScore = computed(() => (
  Number.isInteger(score.value) ? score.value : score.value?.toFixed(1)
))
const scorePercent = computed(() => (score.value || 0) * 10)

const renderedReport = computed(() => (
  renderAccessibleMarkdown(props.reportText, {
    code: '简历报告代码块，可横向滚动',
    table: '简历报告表格，可横向滚动'
  })
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
  min-width: 0;
  gap: var(--space-4);
}

.drawer-heading__icon {
  position: relative;
  display: grid;
  width: 2.75rem;
  height: 2.75rem;
  flex: 0 0 2.75rem;
  place-items: center;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-control);
  background:
    linear-gradient(var(--color-surface-elevated), var(--color-surface-elevated)) padding-box,
    var(--aurora-gradient) border-box;
  color: var(--color-primary-text);
  box-shadow: 0 0 1.5rem var(--color-aurora-violet-soft);
  font-size: 1.35rem;
}

.drawer-heading .technical-label {
  margin: 0 0 var(--space-1);
}

.drawer-heading h2 {
  margin: 0;
  font-size: var(--font-size-component-title);
  line-height: var(--line-height-component-title);
  letter-spacing: -.015em;
}

.report-panel {
  display: grid;
  gap: var(--space-8);
  padding-bottom: var(--space-6);
}

.report-state,
.score-unavailable {
  display: grid;
  justify-items: center;
  min-height: 20rem;
  padding: var(--space-12) var(--space-6);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-panel);
  background:
    radial-gradient(circle at 50% 36%, var(--color-aurora-cyan-soft), transparent 10rem),
    var(--color-surface-subtle);
  color: var(--color-text-muted);
  text-align: center;
}

.report-state__visual {
  position: relative;
  display: grid;
  width: 5.5rem;
  height: 5.5rem;
  margin-bottom: var(--space-5);
  place-items: center;
}

.report-state__visual::before,
.report-state__orbit {
  position: absolute;
  border: 1px solid var(--color-orbit);
  border-radius: 50%;
  content: '';
}

.report-state__visual::before {
  inset: .65rem;
  border-color: var(--color-border-strong);
  background: var(--color-surface-elevated);
  box-shadow: var(--aurora-glow);
}

.report-state__orbit {
  inset: 0;
}

.report-state__orbit::after {
  position: absolute;
  top: .35rem;
  left: 50%;
  width: .5rem;
  height: .5rem;
  border-radius: 50%;
  background: var(--color-cyan);
  box-shadow: 0 0 1rem var(--color-cyan);
  content: '';
  transform: translateX(-50%);
}

.report-state__visual > .el-icon {
  position: relative;
  color: var(--color-cyan);
  font-size: 1.65rem;
}

.report-state .technical-label {
  margin: 0 0 var(--space-2);
  color: var(--color-cyan);
}

.report-state h3,
.score-unavailable h3 {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-component-title);
}

.report-state p,
.score-unavailable p {
  max-width: 28rem;
  margin: 0;
  color: var(--color-text-secondary);
}

.score-overview {
  position: relative;
  display: grid;
  grid-template-columns: minmax(9rem, .85fr) minmax(0, 1.15fr);
  align-items: center;
  gap: var(--space-5);
  min-height: 12rem;
  padding: var(--space-6);
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-panel);
  background:
    radial-gradient(circle at 12% 0, var(--color-aurora-violet-soft), transparent 15rem),
    var(--color-surface-subtle);
  box-shadow: var(--shadow-card);
}

.score-overview::after {
  position: absolute;
  right: var(--space-5);
  bottom: 0;
  left: var(--space-5);
  height: 1px;
  background: var(--aurora-gradient);
  content: '';
  opacity: .7;
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
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-component-title);
}

.score-value {
  display: block;
  margin-bottom: var(--space-3);
  color: var(--color-primary-text);
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
  position: relative;
  grid-template-columns: auto minmax(0, 1fr) auto;
  justify-items: start;
  align-items: start;
  gap: var(--space-4);
  min-height: 0;
  padding: var(--space-6);
  border-style: solid;
  border-color: color-mix(in srgb, var(--color-warning) 52%, var(--color-border));
  background:
    radial-gradient(circle at 100% 0, var(--color-warning-soft), transparent 18rem),
    var(--color-surface-subtle);
  text-align: left;
}

.score-unavailable > .el-icon {
  margin-top: .2rem;
  color: var(--color-warning-text);
  font-size: 1.35rem;
}

.score-unavailable .technical-label {
  margin: 0 0 var(--space-1);
  color: var(--color-text-muted);
}

.score-unavailable__copy {
  min-width: 0;
}

.score-unavailable__value {
  align-self: center;
  padding-left: var(--space-4);
  color: var(--color-warning-text);
  font-size: clamp(2rem, 6vw, 3.5rem);
  font-weight: 300;
  line-height: 1;
}

.report-content {
  position: relative;
  padding-top: var(--space-8);
  border-top: 1px solid var(--color-border);
}

.report-content::before {
  position: absolute;
  top: -1px;
  left: 0;
  width: 5rem;
  height: 1px;
  background: var(--aurora-gradient);
  content: '';
}

.report-content__heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.report-content__heading .technical-label {
  margin: 0 0 var(--space-1);
}

.report-content__heading h3 {
  margin: 0;
  font-size: var(--font-size-component-title);
}

.report-content__status {
  padding: .35rem .65rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: var(--color-surface-subtle);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  line-height: 1;
  white-space: nowrap;
}

.report-markdown {
  max-width: 70ch;
  overflow-wrap: anywhere;
  color: var(--color-text-secondary);
  font-size: var(--font-size-body);
  line-height: 1.8;
}

.report-markdown :deep(h1),
.report-markdown :deep(h2),
.report-markdown :deep(h3),
.report-markdown :deep(h4) {
  margin: var(--space-8) 0 var(--space-3);
  color: var(--color-text-primary);
  font-size: var(--font-size-component-title);
  line-height: var(--line-height-component-title);
}

.report-markdown :deep(h1),
.report-markdown :deep(h2) {
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border);
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
  margin: 0 0 var(--space-4);
}

.report-markdown :deep(ul),
.report-markdown :deep(ol) {
  padding-left: var(--space-5);
}

.report-markdown :deep(li + li) {
  margin-top: var(--space-2);
}

.report-markdown :deep(strong) {
  color: var(--color-primary-text);
}

.report-markdown :deep(blockquote) {
  padding: var(--space-3) var(--space-4);
  border-left: 2px solid var(--color-cyan);
  background: linear-gradient(90deg, var(--color-aurora-cyan-soft), transparent);
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
  max-width: 100%;
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

.report-markdown :deep(table) {
  display: block;
  width: 100%;
  max-width: 100%;
  margin: var(--space-4) 0;
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  border-collapse: separate;
  border-spacing: 0;
  background: var(--color-surface-subtle);
  white-space: nowrap;
}

.report-markdown :deep(th),
.report-markdown :deep(td) {
  padding: var(--space-2) var(--space-3);
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  text-align: left;
}

.report-markdown :deep(th) {
  background: var(--color-primary-soft);
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
}

.report-markdown :deep(tr:last-child td) {
  border-bottom: 0;
}

.report-markdown :deep(th:last-child),
.report-markdown :deep(td:last-child) {
  border-right: 0;
}

.report-markdown :deep(a) {
  color: var(--color-primary-text);
  text-decoration-color: color-mix(in srgb, var(--color-primary) 55%, transparent);
  text-underline-offset: .2em;
}

.report-markdown :deep(hr) {
  height: 1px;
  margin: var(--space-8) 0;
  border: 0;
  background: var(--color-border);
}

@media (max-width: 440px) {
  .drawer-heading {
    gap: var(--space-3);
  }

  .drawer-heading__icon {
    width: 2.5rem;
    height: 2.5rem;
    flex-basis: 2.5rem;
  }

  .score-overview {
    grid-template-columns: 1fr;
    padding: var(--space-5);
  }

  .score-chart {
    width: min(100%, 12rem);
    margin: 0 auto;
  }

  .score-unavailable {
    grid-template-columns: auto minmax(0, 1fr);
    padding: var(--space-5);
  }

  .score-unavailable__value {
    grid-column: 2;
    padding: 0;
    font-size: 2.5rem;
  }

  .report-content__heading {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .drawer-heading__icon,
  .report-state,
  .score-overview,
  .score-unavailable {
    background: var(--color-surface-subtle);
  }
}
</style>
