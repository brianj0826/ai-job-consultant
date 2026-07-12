<template>
  <section
    v-if="active"
    class="interview-bar"
    :class="statusToneClass"
    aria-label="模拟面试进度"
    aria-live="polite"
  >
    <div class="interview-status">
      <div class="interview-status__icon" aria-hidden="true">
        <el-icon><Microphone /></el-icon>
      </div>
      <div class="interview-status__copy">
        <span class="technical-label">{{ statusLabel }}</span>
        <strong>{{ title || '模拟面试' }}</strong>
      </div>
    </div>

    <div class="interview-progress" :class="{ 'interview-progress--empty': total < 1 }">
      <div class="interview-progress__meta">
        <span class="interview-progress__label tabular-nums">
          {{ total > 0 ? `第 ${current} / ${total} 题` : '暂未添加题目' }}
        </span>
        <span v-if="total > 0" class="interview-progress__percentage tabular-nums">
          {{ progressPercentage }}%
        </span>
      </div>
      <el-progress
        class="interview-progress__bar"
        :percentage="progressPercentage"
        :show-text="false"
        :stroke-width="6"
        color="var(--interview-accent)"
        :aria-label="progressAriaLabel"
      />
    </div>

    <div class="interview-actions">
      <span v-if="hasScore" class="interview-score">
        <span class="technical-label">SCORE</span>
        <strong class="tabular-nums">{{ score }} / 100</strong>
      </span>
      <el-button
        v-if="status === 'in_progress'"
        class="interview-action interview-action--end"
        plain
        type="danger"
        @click="emit('end')"
      >
        <el-icon aria-hidden="true"><VideoPause /></el-icon>
        结束面试
      </el-button>
      <el-button v-else class="interview-action" type="primary" @click="emit('start')">
        <el-icon aria-hidden="true"><Microphone /></el-icon>
        {{ status === 'completed' ? '继续训练' : '开始面试' }}
      </el-button>
      <el-button
        class="interview-action interview-action--score"
        :type="status === 'in_progress' ? 'primary' : undefined"
        @click="emit('score')"
      >
        <el-icon aria-hidden="true"><DataAnalysis /></el-icon>
        查看题目与评分
      </el-button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { DataAnalysis, Microphone, VideoPause } from '@element-plus/icons-vue'

const props = defineProps({
  active: { type: Boolean, default: false },
  title: { type: String, default: '' },
  status: { type: String, default: 'in_progress' },
  current: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  score: { type: [Number, String], default: null }
})
const emit = defineEmits(['start', 'end', 'score'])

const statusLabel = computed(() => ({
  planned: 'PLANNED PRACTICE',
  in_progress: 'LIVE PRACTICE',
  completed: 'REVIEW READY',
  cancelled: 'PAUSED PRACTICE'
}[props.status] || 'INTERVIEW PRACTICE'))

const statusToneClass = computed(() => ({
  planned: 'interview-bar--planned',
  in_progress: 'interview-bar--live',
  completed: 'interview-bar--completed',
  cancelled: 'interview-bar--paused'
}[props.status] || 'interview-bar--neutral'))

const hasScore = computed(() => (
  props.score !== null
  && props.score !== undefined
  && String(props.score).trim() !== ''
))

const progressPercentage = computed(() => {
  if (!props.total || props.total < 1) return 0
  return Math.min(100, Math.max(0, Math.round((props.current / props.total) * 100)))
})

const progressAriaLabel = computed(() => (
  props.total > 0
    ? `面试进度：第 ${props.current} 题，共 ${props.total} 题，已完成 ${progressPercentage.value}%`
    : '面试进度：暂未添加题目'
))
</script>

<style scoped>
.interview-bar {
  --interview-accent: var(--color-primary);

  position: relative;
  display: grid;
  grid-template-columns: minmax(14rem, .85fr) minmax(15rem, 1fr) auto;
  align-items: center;
  gap: clamp(var(--space-4), 2.4vw, var(--space-8));
  isolation: isolate;
  min-width: 0;
  overflow: hidden;
  flex-shrink: 0;
  padding: var(--space-5) clamp(var(--space-5), 2.6vw, var(--space-8));
  border: 1px solid color-mix(in srgb, var(--interview-accent) 20%, var(--color-border));
  border-radius: var(--radius-card);
  background:
    linear-gradient(115deg, color-mix(in srgb, var(--interview-accent) 8%, transparent), transparent 38%),
    var(--color-surface-elevated);
  box-shadow: var(--shadow-card);
}

.interview-bar::before {
  position: absolute;
  z-index: -1;
  width: 16rem;
  height: 16rem;
  border: 1px solid color-mix(in srgb, var(--interview-accent) 12%, transparent);
  border-radius: 50%;
  content: "";
  inset: -12rem auto auto -8rem;
  pointer-events: none;
}

.interview-bar--live {
  --interview-accent: var(--color-cyan);
}

.interview-bar--completed {
  --interview-accent: var(--color-success);
}

.interview-bar--paused {
  --interview-accent: var(--color-warning);
}

.interview-status {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  min-width: 0;
  padding-right: clamp(var(--space-4), 2vw, var(--space-8));
}

.interview-status::after {
  position: absolute;
  width: 1px;
  background: var(--color-border);
  content: "";
  inset-block: calc(var(--space-2) * -1);
  right: 0;
}

.interview-status__icon {
  position: relative;
  display: grid;
  width: 3rem;
  height: 3rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--interview-accent) 38%, var(--color-border));
  border-radius: 50%;
  background: color-mix(in srgb, var(--interview-accent) 10%, var(--color-surface));
  box-shadow: 0 0 1.75rem color-mix(in srgb, var(--interview-accent) 18%, transparent);
  color: var(--interview-accent);
  font-size: 1.55rem;
}

.interview-status__icon::after {
  position: absolute;
  border: 1px solid color-mix(in srgb, var(--interview-accent) 18%, transparent);
  border-radius: inherit;
  content: "";
  inset: -.35rem;
}

.interview-status__copy {
  display: grid;
  gap: .35rem;
  min-width: 0;
}

.interview-status__copy .technical-label {
  margin: 0;
  color: color-mix(in srgb, var(--interview-accent) 72%, var(--color-text-muted));
  white-space: nowrap;
}

.interview-status__copy strong {
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: 1.05rem;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.interview-progress {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.interview-progress__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.interview-progress__label {
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-label);
  white-space: nowrap;
}

.interview-progress__percentage {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
}

.interview-progress--empty .interview-progress__label {
  color: var(--color-text-muted);
}

.interview-progress :deep(.el-progress-bar__outer) {
  background: color-mix(in srgb, var(--color-text-muted) 13%, transparent);
}

.interview-progress :deep(.el-progress-bar__inner) {
  background-image: linear-gradient(90deg, var(--color-primary), var(--interview-accent));
  box-shadow: 0 0 .75rem color-mix(in srgb, var(--interview-accent) 32%, transparent);
}

.interview-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: var(--space-2);
}

.interview-score {
  display: grid;
  flex: 0 0 auto;
  gap: .1rem;
  min-width: 4.75rem;
  padding: .35rem var(--space-3);
  border-right: 1px solid var(--color-border);
  color: var(--color-text-primary);
  line-height: 1.2;
}

.interview-score .technical-label {
  color: var(--color-text-muted);
  font-size: .625rem;
}

.interview-score strong {
  font-size: var(--font-size-label);
}

.interview-actions :deep(.el-button) {
  min-height: 44px;
  margin-left: 0;
  padding-inline: var(--space-4);
  font-weight: 650;
}

.interview-action--end:hover,
.interview-action--end:focus-visible {
  box-shadow: 0 0 0 3px var(--color-danger-soft);
}

:global(html.dark) .interview-bar {
  background:
    linear-gradient(115deg, color-mix(in srgb, var(--interview-accent) 9%, transparent), transparent 42%),
    color-mix(in srgb, var(--color-surface-elevated) 91%, var(--color-canvas-deep));
  box-shadow:
    0 1px 0 rgb(255 255 255 / 2%) inset,
    0 16px 38px rgb(0 0 0 / 22%);
}

@media (max-width: 1099px) {
  .interview-bar {
    grid-template-columns: minmax(13rem, .8fr) minmax(14rem, 1fr);
  }

  .interview-actions {
    grid-column: 1 / -1;
    justify-content: flex-end;
    padding-top: var(--space-1);
    border-top: 1px solid var(--color-border);
  }
}

@media (max-width: 767px) {
  .interview-bar {
    grid-template-columns: minmax(0, 1fr);
    align-items: stretch;
    gap: var(--space-4);
    padding: var(--space-5);
  }

  .interview-status {
    padding-right: 0;
  }

  .interview-status::after {
    display: none;
  }

  .interview-status__copy strong {
    white-space: normal;
  }

  .interview-progress {
    width: 100%;
    padding-block: var(--space-4);
    border-block: 1px solid var(--color-border);
  }

  .interview-actions {
    display: grid;
    grid-column: auto;
    grid-template-columns: 1fr 1fr;
    padding-top: 0;
    border-top: 0;
  }

  .interview-score {
    grid-column: 1 / -1;
    grid-template-columns: auto 1fr;
    min-height: 44px;
    align-items: center;
    padding-inline: 0;
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .interview-score strong {
    justify-self: end;
  }

  .interview-actions :deep(.el-button) {
    width: 100%;
    padding-inline: var(--space-2);
    white-space: normal;
  }
}

@media (max-width: 419px) {
  .interview-actions {
    grid-template-columns: 1fr;
  }

  .interview-score {
    grid-column: auto;
  }
}
</style>
