<template>
  <el-drawer
    v-model="visible"
    class="match-drawer"
    direction="rtl"
    size="var(--panel-width)"
  >
    <template #header>
      <div class="drawer-heading">
        <div class="drawer-heading__icon" aria-hidden="true">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <div>
          <p class="technical-label">ROLE ALIGNMENT</p>
          <h2>岗位匹配分析</h2>
        </div>
      </div>
    </template>

    <section class="match-panel" aria-label="岗位匹配分析报告">
      <div v-if="!reportText" class="report-state" role="status">
        <el-icon aria-hidden="true"><Document /></el-icon>
        <h3>暂无匹配结果</h3>
        <p>粘贴职位描述并发起“匹配岗位”，即可查看真实的技能与匹配分析。</p>
      </div>

      <template v-else>
        <section v-if="hasMatchScore" class="match-overview" aria-labelledby="match-score-title">
          <el-progress
            class="match-gauge"
            type="dashboard"
            :percentage="matchPercent"
            :color="gaugeColor"
            :stroke-width="12"
            :width="152"
          >
            <template #default="{ percentage }">
              <span class="gauge-value tabular-nums">{{ percentage }}%</span>
            </template>
          </el-progress>
          <div class="match-copy">
            <p class="technical-label">ROLE ALIGNMENT</p>
            <h3 id="match-score-title">综合匹配度</h3>
            <span :class="['match-status', `match-status--${matchStatus.tone}`]">
              {{ matchStatus.label }}
            </span>
            <p>匹配度由本次简历与职位描述的分析结果提供。</p>
          </div>
        </section>

        <section v-else class="score-unavailable" aria-labelledby="match-score-unavailable-title">
          <el-icon aria-hidden="true"><WarningFilled /></el-icon>
          <div>
            <p class="technical-label">SCORE UNAVAILABLE</p>
            <h3 id="match-score-unavailable-title">未解析到匹配度</h3>
            <p>报告正文仍可查看；系统不会用默认百分比替代实际分析结果。</p>
          </div>
        </section>

        <section class="skill-section" aria-labelledby="skill-compare-title">
          <div class="report-section-heading">
            <div>
              <p class="technical-label">SKILL SIGNALS</p>
              <h3 id="skill-compare-title">技能对比</h3>
            </div>
          </div>

          <div class="skill-grid">
            <article class="skill-card skill-card--matched">
              <div class="skill-card__heading">
                <el-icon aria-hidden="true"><CircleCheckFilled /></el-icon>
                <h4>已匹配技能</h4>
              </div>
              <div v-if="matchedSkills.length" class="skill-list">
                <el-tag v-for="skill in matchedSkills" :key="skill" class="skill-tag skill-tag--matched" effect="plain">
                  {{ skill }}
                </el-tag>
              </div>
              <p v-else class="skill-empty">报告中未解析到明确的匹配技能。</p>
            </article>

            <article class="skill-card skill-card--missing">
              <div class="skill-card__heading">
                <el-icon aria-hidden="true"><WarningFilled /></el-icon>
                <h4>待补充技能</h4>
              </div>
              <div v-if="missingSkills.length" class="skill-list">
                <el-tag v-for="skill in missingSkills" :key="skill" class="skill-tag skill-tag--missing" effect="plain">
                  {{ skill }}
                </el-tag>
              </div>
              <p v-else class="skill-empty">报告中未解析到明确的待补充技能。</p>
            </article>
          </div>
        </section>

        <section class="report-content" aria-labelledby="match-report-content-title">
          <div class="report-section-heading">
            <div>
              <p class="technical-label">ANALYSIS DETAILS</p>
              <h3 id="match-report-content-title">完整分析</h3>
            </div>
          </div>
          <div class="report-markdown" v-html="renderedReport"></div>
        </section>
      </template>
    </section>
  </el-drawer>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  CircleCheckFilled,
  DataAnalysis,
  Document,
  WarningFilled
} from '@element-plus/icons-vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

const props = defineProps({
  reportText: { type: String, default: '' }
})

const visible = ref(false)

const matchPercent = computed(() => {
  const primaryMatch = props.reportText.match(/(?:综合)?匹配度[^\n：:]*[：:]\s*(\d+(?:\.\d+)?)\s*%?/i)
  const fallbackMatch = props.reportText.match(/(\d+(?:\.\d+)?)\s*%/)
  const value = Number(primaryMatch?.[1] || fallbackMatch?.[1])

  return Number.isFinite(value) && value >= 0 && value <= 100 ? Math.round(value) : null
})

const hasMatchScore = computed(() => matchPercent.value !== null)

const matchStatus = computed(() => {
  if (matchPercent.value === null) return { label: '未解析', tone: 'neutral' }
  if (matchPercent.value >= 70) return { label: '匹配度较高', tone: 'success' }
  if (matchPercent.value >= 40) return { label: '存在提升空间', tone: 'warning' }
  return { label: '需要重点补强', tone: 'danger' }
})

const gaugeColor = computed(() => {
  const color = matchStatus.value.tone === 'success'
    ? 'var(--color-success)'
    : matchStatus.value.tone === 'warning'
      ? 'var(--color-warning)'
      : 'var(--color-danger)'
  return [{ color, offset: 0 }, { color, offset: 100 }]
})

const extractSkills = (sectionName, stopNames) => {
  if (!props.reportText) return []
  const stopPattern = stopNames.join('|')
  const section = props.reportText.match(new RegExp(
    `(?:${sectionName})\\s*[：:]?\\s*([\\s\\S]*?)(?=(?:${stopPattern})\\s*[：:]|$)`,
    'i'
  ))
  if (!section) return []

  const skills = section[1]
    .split('\n')
    .map((line) => line
      .replace(/^\s*(?:[-*•]|\d+[.、)）])\s*/, '')
      .replace(/\*\*/g, '')
      .trim()
    )
    .filter(Boolean)
    .map((skill) => skill.slice(0, 32))

  return [...new Set(skills)].slice(0, 6)
}

const matchedSkills = computed(() => extractSkills('匹配的技能', ['缺失的技能', '加分项', '建议']))
const missingSkills = computed(() => extractSkills('缺失的技能', ['加分项', '建议']))
const renderedReport = computed(() => (
  props.reportText ? DOMPurify.sanitize(marked(props.reportText)) : ''
))

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

.drawer-heading .technical-label,
.report-section-heading .technical-label {
  margin: 0 0 var(--space-1);
}

.drawer-heading h2,
.report-section-heading h3 {
  margin: 0;
  font-size: var(--font-size-component-title);
  line-height: var(--line-height-component-title);
}

.match-panel {
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

.match-overview {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-5);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-panel);
  background: var(--color-surface-subtle);
  box-shadow: var(--shadow-card);
}

.match-gauge {
  display: grid;
  place-items: center;
}

.gauge-value {
  color: var(--color-text-primary);
  font-size: 1.5rem;
  font-weight: 700;
}

.match-copy .technical-label {
  margin: 0 0 var(--space-2);
}

.match-copy h3 {
  margin-bottom: var(--space-3);
  font-size: var(--font-size-component-title);
}

.match-copy > p:last-child {
  margin: var(--space-3) 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  line-height: var(--line-height-body);
}

.match-status {
  display: inline-flex;
  align-items: center;
  min-height: 1.75rem;
  padding: 0 var(--space-3);
  border-radius: var(--radius-pill);
  font-size: var(--font-size-caption);
  font-weight: 650;
}

.match-status--success {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.match-status--warning {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.match-status--danger {
  background: var(--color-danger-soft);
  color: var(--color-danger);
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

.skill-section,
.report-content {
  padding-top: var(--space-6);
  border-top: 1px solid var(--color-border);
}

.report-section-heading {
  margin-bottom: var(--space-4);
}

.skill-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.skill-card {
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface-subtle);
}

.skill-card__heading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.skill-card__heading h4 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
}

.skill-card--matched .skill-card__heading .el-icon {
  color: var(--color-success);
}

.skill-card--missing .skill-card__heading .el-icon {
  color: var(--color-warning);
}

.skill-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.skill-tag {
  max-width: 100%;
}

.skill-tag--matched {
  --el-tag-bg-color: var(--color-success-soft);
  --el-tag-border-color: var(--color-success);
  --el-tag-text-color: var(--color-success);
}

.skill-tag--missing {
  --el-tag-bg-color: var(--color-warning-soft);
  --el-tag-border-color: var(--color-warning);
  --el-tag-text-color: var(--color-warning);
}

.skill-empty {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-body);
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
  .match-overview,
  .skill-grid {
    grid-template-columns: 1fr;
  }

  .match-gauge {
    justify-self: center;
  }
}
</style>
