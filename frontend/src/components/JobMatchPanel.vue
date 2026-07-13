<template>
  <InsightDrawerShell
    v-model="visible"
    class="match-drawer"
  >
    <template #header="{ titleId, titleClass }">
      <div class="drawer-heading">
        <div class="drawer-heading__icon" aria-hidden="true">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <div>
          <p class="technical-label">ROLE ALIGNMENT</p>
          <h2 :id="titleId" :class="titleClass">岗位匹配分析</h2>
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
          <div class="match-gauge-frame">
            <el-progress
              class="match-gauge"
              type="dashboard"
              :percentage="matchPercent"
              :color="gaugeColor"
              :stroke-width="10"
              :width="136"
            >
              <template #default="{ percentage }">
                <span class="gauge-value tabular-nums">{{ percentage }}<small>%</small></span>
              </template>
            </el-progress>
          </div>
          <div class="match-copy">
            <p class="technical-label">MATCH SCORE · LIVE ANALYSIS</p>
            <h3 id="match-score-title">综合匹配度</h3>
            <span :class="['match-status', `match-status--${matchStatus.tone}`]">
              <span class="match-status__dot" aria-hidden="true"></span>
              {{ matchStatus.label }}
            </span>
            <p>该数值直接来自本次简历与职位描述的分析结果。</p>
          </div>
        </section>

        <section v-else class="score-unavailable" aria-labelledby="match-score-unavailable-title">
          <div class="score-unavailable__icon" aria-hidden="true">
            <el-icon><WarningFilled /></el-icon>
          </div>
          <div class="score-unavailable__copy">
            <p class="technical-label">SCORE UNAVAILABLE</p>
            <h3 id="match-score-unavailable-title">未解析到匹配度</h3>
            <p>报告正文仍可查看；系统不会用默认百分比替代实际分析结果。</p>
          </div>
          <strong class="score-unavailable__value tabular-nums" aria-label="匹配度未解析">—</strong>
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
                <span class="skill-card__icon" aria-hidden="true">
                  <el-icon><CircleCheckFilled /></el-icon>
                </span>
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
                <span class="skill-card__icon" aria-hidden="true">
                  <el-icon><WarningFilled /></el-icon>
                </span>
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
  </InsightDrawerShell>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  CircleCheckFilled,
  DataAnalysis,
  Document,
  WarningFilled
} from '@element-plus/icons-vue'
import { renderAccessibleMarkdown } from '../utils/markdownAccessibility'
import InsightDrawerShell from './InsightDrawerShell.vue'

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
  const normalizeHeading = (line) => line
    .replace(/^\s*#{1,6}\s+/, '')
    .replace(/^\s*\d+[.、)）]\s*/, '')
    .replace(/\*\*/g, '')
    .trim()
  const isStopHeading = (line) => stopNames.some((name) => (
    line === name
    || line.startsWith(`${name}：`)
    || line.startsWith(`${name}:`)
  ))
  const skills = []
  let collecting = false

  for (const rawLine of props.reportText.split('\n')) {
    const heading = normalizeHeading(rawLine)

    if (!collecting) {
      const sectionMatch = heading.match(new RegExp(`^${sectionName}(?:\\s*[：:]\\s*(.*)|\\s*)$`, 'i'))
      if (!sectionMatch) continue
      collecting = true
      if (sectionMatch[1]) skills.push(...sectionMatch[1].split(/[、，,]/))
      continue
    }

    if (isStopHeading(heading) || /^\s*#{1,6}\s+/.test(rawLine)) break

    const skillLine = rawLine
      .replace(/^\s*(?:[-*•]|\d+[.、)）])\s*/, '')
      .replace(/\*\*/g, '')
      .trim()
    if (skillLine) skills.push(...skillLine.split(/[、，,]/))
  }

  const normalizedSkills = skills
    .map((skill) => skill.trim())
    .filter(Boolean)
    .filter((skill) => !isStopHeading(normalizeHeading(skill)))
    .map((skill) => skill.slice(0, 32))

  return [...new Set(normalizedSkills)].slice(0, 6)
}

const matchedSkills = computed(() => extractSkills('匹配的技能', ['缺失的技能', '加分项', '建议']))
const missingSkills = computed(() => extractSkills('缺失的技能', ['加分项', '建议']))
const renderedReport = computed(() => (
  renderAccessibleMarkdown(props.reportText, {
    code: '岗位匹配报告代码块，可横向滚动',
    table: '岗位匹配报告表格，可横向滚动'
  })
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
  min-width: 0;
  gap: var(--space-4);
}

.drawer-heading__icon {
  position: relative;
  display: grid;
  width: 3rem;
  height: 3rem;
  flex: 0 0 3rem;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--color-primary) 62%, var(--color-border));
  border-radius: .375rem;
  background:
    linear-gradient(145deg, var(--color-aurora-violet-soft), var(--color-aurora-blue-soft)),
    var(--color-surface-subtle);
  box-shadow:
    inset 0 0 0 1px color-mix(in srgb, var(--color-cyan) 24%, transparent),
    0 0 24px var(--color-aurora-violet-soft);
  color: var(--color-cyan);
  font-size: 1.45rem;
}

.drawer-heading .technical-label,
.report-section-heading .technical-label {
  margin: 0 0 var(--space-1);
  color: color-mix(in srgb, var(--color-info) 78%, var(--color-text-secondary));
  letter-spacing: .08em;
}

.drawer-heading h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 1.4rem;
  line-height: 1.2;
  letter-spacing: -.02em;
}

.report-section-heading h3 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-section-title);
  line-height: var(--line-height-section-title);
  letter-spacing: -.02em;
}

.match-panel {
  display: grid;
  gap: var(--space-8);
  padding-bottom: var(--space-8);
}

.report-state,
.score-unavailable {
  position: relative;
  overflow: hidden;
  display: grid;
  justify-items: center;
  min-height: 22rem;
  align-content: center;
  padding: var(--space-10) var(--space-6);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-panel);
  background:
    radial-gradient(circle at 50% 32%, var(--color-aurora-blue-soft), transparent 13rem),
    linear-gradient(145deg, color-mix(in srgb, var(--color-surface-subtle) 94%, transparent), var(--color-surface-elevated));
  color: var(--color-text-muted);
  text-align: center;
}

.report-state > .el-icon {
  display: grid;
  width: 4.5rem;
  height: 4.5rem;
  place-items: center;
  margin-bottom: var(--space-5);
  border: 1px solid color-mix(in srgb, var(--color-cyan) 38%, var(--color-border));
  border-radius: 50%;
  background: var(--color-aurora-cyan-soft);
  box-shadow: 0 0 0 1rem color-mix(in srgb, var(--color-aurora-cyan-soft) 48%, transparent);
  color: var(--color-cyan);
  font-size: 1.65rem;
}

.report-state h3,
.score-unavailable h3 {
  margin-top: 0;
  margin-bottom: var(--space-2);
  color: var(--color-text-primary);
  font-size: var(--font-size-section-title);
}

.report-state p,
.score-unavailable p {
  max-width: 28rem;
  margin: 0;
  color: var(--color-text-secondary);
}

.match-overview {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: 9.5rem minmax(0, 1fr);
  align-items: center;
  gap: var(--space-6);
  min-height: 12.5rem;
  padding: var(--space-6);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-panel);
  background:
    linear-gradient(100deg, var(--color-aurora-violet-soft), transparent 46%),
    var(--color-surface-subtle);
  box-shadow: var(--shadow-card);
}

.match-overview::after {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 2px;
  background: var(--aurora-gradient);
  content: '';
  opacity: .82;
}

.match-gauge-frame {
  display: grid;
  min-height: 9.5rem;
  place-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: color-mix(in srgb, var(--color-surface-elevated) 70%, transparent);
}

.match-gauge {
  display: grid;
  place-items: center;
}

.match-gauge :deep(.el-progress-circle__track) {
  stroke: color-mix(in srgb, var(--color-border-strong) 65%, transparent);
}

.gauge-value {
  color: var(--color-text-primary);
  font-size: 1.75rem;
  font-weight: 760;
  letter-spacing: -.04em;
}

.gauge-value small {
  margin-left: .1em;
  color: var(--color-text-muted);
  font-size: .7rem;
  font-weight: 600;
  letter-spacing: 0;
}

.match-copy .technical-label {
  margin: 0 0 var(--space-2);
  color: var(--color-text-muted);
}

.match-copy h3 {
  margin: 0 0 var(--space-3);
  color: var(--color-text-primary);
  font-size: var(--font-size-section-title);
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
  gap: var(--space-2);
  min-height: 1.75rem;
  padding: 0 var(--space-3);
  border: 1px solid currentColor;
  border-radius: var(--radius-pill);
  font-size: var(--font-size-caption);
  font-weight: 650;
}

.match-status__dot {
  width: .4rem;
  height: .4rem;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 .65rem currentColor;
}

.match-status--success {
  background: var(--color-success-soft);
  color: var(--color-success-text);
}

.match-status--warning {
  background: var(--color-warning-soft);
  color: var(--color-warning-text);
}

.match-status--danger {
  background: var(--color-danger-soft);
  color: var(--color-danger-text);
}

.score-unavailable {
  grid-template-columns: auto minmax(0, 1fr) auto;
  justify-items: start;
  min-height: 0;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  border: 1px solid color-mix(in srgb, var(--color-warning) 52%, var(--color-border));
  background:
    linear-gradient(100deg, var(--color-warning-soft), transparent 72%),
    var(--color-surface-subtle);
  box-shadow: inset 0 0 28px color-mix(in srgb, var(--color-warning-soft) 32%, transparent);
  text-align: left;
}

.score-unavailable__icon {
  display: grid;
  width: 2.5rem;
  height: 2.5rem;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--color-warning) 42%, var(--color-border));
  border-radius: var(--radius-control);
  background: var(--color-warning-soft);
  color: var(--color-warning-text);
  font-size: 1.25rem;
}

.score-unavailable .technical-label {
  margin: 0 0 var(--space-1);
  color: var(--color-text-muted);
}

.score-unavailable__copy {
  min-width: 0;
}

.score-unavailable__copy h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-size-component-title);
}

.score-unavailable__value {
  color: color-mix(in srgb, var(--color-warning) 78%, var(--color-text-primary));
  font-size: 2.4rem;
  font-weight: 500;
  line-height: 1;
}

.skill-section,
.report-content {
  padding-top: var(--space-7);
  border-top: 1px solid var(--color-border);
}

.report-section-heading {
  margin-bottom: var(--space-4);
}

.skill-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.skill-card {
  position: relative;
  overflow: hidden;
  min-width: 0;
  min-height: 10.5rem;
  padding: var(--space-5);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-card);
  background: var(--color-surface-subtle);
}

.skill-card::after {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 2px;
  background: currentColor;
  content: '';
  opacity: .85;
}

.skill-card--matched {
  border-color: color-mix(in srgb, var(--color-success) 38%, var(--color-border));
  background:
    linear-gradient(145deg, var(--color-success-soft), transparent 76%),
    var(--color-surface-subtle);
  color: var(--color-success-text);
}

.skill-card--missing {
  border-color: color-mix(in srgb, var(--color-warning) 42%, var(--color-border));
  background:
    linear-gradient(145deg, var(--color-warning-soft), transparent 76%),
    var(--color-surface-subtle);
  color: var(--color-warning-text);
}

.skill-card__heading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.skill-card__heading h4 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-component-title);
}

.skill-card__icon {
  display: grid;
  width: 2rem;
  height: 2rem;
  flex: 0 0 2rem;
  place-items: center;
  border: 1px solid currentColor;
  border-radius: 50%;
  background: color-mix(in srgb, currentColor 9%, transparent);
  color: inherit;
  font-size: 1.05rem;
}

.skill-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.skill-tag {
  max-width: 100%;
  min-height: 1.75rem;
  border-radius: var(--radius-pill);
}

.skill-tag--matched {
  --el-tag-bg-color: var(--color-success-soft);
  --el-tag-border-color: var(--color-success);
  --el-tag-text-color: var(--color-success-text);
}

.skill-tag--missing {
  --el-tag-bg-color: var(--color-warning-soft);
  --el-tag-border-color: var(--color-warning);
  --el-tag-text-color: var(--color-warning-text);
}

.skill-empty {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
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
  color: var(--color-primary-text);
}

.report-markdown :deep(a) {
  color: var(--color-cyan);
  text-underline-offset: .2em;
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

@media (max-width: 560px) {
  .drawer-heading {
    gap: var(--space-3);
  }

  .drawer-heading__icon {
    width: 2.625rem;
    height: 2.625rem;
    flex-basis: 2.625rem;
    font-size: 1.25rem;
  }

  .drawer-heading h2 {
    font-size: 1.15rem;
  }

  .match-panel {
    gap: var(--space-6);
  }

  .match-overview,
  .skill-grid {
    grid-template-columns: 1fr;
  }

  .match-overview {
    gap: var(--space-4);
    padding: var(--space-4);
  }

  .match-gauge-frame {
    min-height: 9rem;
  }

  .match-gauge {
    justify-self: center;
  }

  .score-unavailable {
    grid-template-columns: auto minmax(0, 1fr);
    padding: var(--space-4);
  }

  .score-unavailable__value {
    display: none;
  }

  .skill-section,
  .report-content {
    padding-top: var(--space-6);
  }

  .skill-card {
    min-height: 0;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .report-state,
  .match-overview,
  .score-unavailable,
  .skill-card {
    background: var(--color-surface-subtle);
  }
}
</style>
