<template>
  <section v-if="active" class="interview-bar" aria-label="模拟面试进度" aria-live="polite">
    <div class="interview-status">
      <div class="interview-status__icon" aria-hidden="true">
        <el-icon><Microphone /></el-icon>
      </div>
      <div class="interview-status__copy">
        <span class="technical-label">{{ statusLabel }}</span>
        <strong>{{ title || '模拟面试' }}</strong>
      </div>
      <div class="interview-progress">
        <span class="interview-progress__label">
          {{ total > 0 ? `第 ${current} / ${total} 题` : '暂未添加题目' }}
        </span>
        <el-progress
          class="interview-progress__bar"
          :percentage="progressPercentage"
          :show-text="false"
          :stroke-width="6"
          color="var(--color-cyan)"
        />
      </div>
    </div>

    <div class="interview-actions">
      <span v-if="score !== null && score !== undefined" class="interview-score tabular-nums">
        {{ score }} / 100
      </span>
      <el-button v-if="status === 'in_progress'" size="small" plain type="danger" @click="emit('end')">
        <el-icon><VideoPause /></el-icon>
        结束面试
      </el-button>
      <el-button v-else size="small" type="primary" @click="emit('start')">
        <el-icon><Microphone /></el-icon>
        {{ status === 'completed' ? '继续训练' : '开始面试' }}
      </el-button>
      <el-button size="small" :type="status === 'in_progress' ? 'primary' : undefined" @click="emit('score')">
        <el-icon><DataAnalysis /></el-icon>
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

const progressPercentage = computed(() => {
  if (!props.total || props.total < 1) return 0
  return Math.min(100, Math.max(0, Math.round((props.current / props.total) * 100)))
})
</script>

<style scoped>
.interview-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-shrink: 0;
  padding: var(--space-3) var(--page-padding);
  border-bottom: 1px solid var(--color-border-strong);
  background: var(--color-surface-elevated);
  box-shadow: var(--shadow-card);
}

.interview-status {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.interview-status__icon {
  display: grid;
  width: 2rem;
  height: 2rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-control);
  background: var(--color-cyan);
  color: var(--color-canvas-deep);
}

.interview-status__copy {
  display: grid;
  gap: var(--space-1);
  min-width: max-content;
}

.interview-status__copy .technical-label {
  margin: 0;
}

.interview-status__copy strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
}

.interview-progress {
  display: grid;
  grid-template-columns: auto minmax(5rem, 7rem);
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
  margin-left: var(--space-3);
}

.interview-progress__label {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  white-space: nowrap;
}

.interview-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: var(--space-2);
}

.interview-score {
  display: inline-flex;
  min-height: 2rem;
  align-items: center;
  padding: 0 var(--space-3);
  border-radius: var(--radius-pill);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: var(--font-size-caption);
  font-weight: 700;
}

@media (max-width: 767px) {
  .interview-bar {
    align-items: stretch;
    flex-direction: column;
    padding: var(--space-3) var(--space-4);
  }

  .interview-status {
    flex-wrap: wrap;
  }

  .interview-progress {
    width: 100%;
    margin-left: 0;
  }

  .interview-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .interview-actions .el-button {
    width: 100%;
  }
}
</style>
