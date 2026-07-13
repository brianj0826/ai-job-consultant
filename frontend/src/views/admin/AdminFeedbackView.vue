<template>
  <section class="admin-page feedback-page" data-testid="admin-feedback-page">
    <section class="admin-panel feedback-panel" aria-labelledby="feedback-review-title">
      <header class="admin-panel__heading admin-panel__heading--wrap feedback-heading">
        <div class="feedback-heading__copy">
          <p class="technical-label">QUALITY REVIEW · HUMAN SIGNALS</p>
          <h2 id="feedback-review-title">反馈审阅</h2>
          <p>逐条检查用户对 AI 回复的真实评价，定位需要改进的回答。</p>
        </div>
        <div class="feedback-heading__controls">
          <span v-if="!loading" class="feedback-total tabular-nums">共 {{ total }} 条</span>
          <el-radio-group v-model="filter" aria-label="反馈类型筛选" @change="applyFilter">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="like">有帮助</el-radio-button>
            <el-radio-button value="dislike">需改进</el-radio-button>
          </el-radio-group>
        </div>
      </header>
      <div v-if="errorMessage" class="admin-inline-error" role="alert">
        <span>
          <strong>反馈列表加载失败</strong>
          <small>{{ errorMessage }}</small>
        </span>
        <el-button text @click="load">重新加载</el-button>
      </div>
      <div
        v-loading="loading"
        class="admin-feedback-list feedback-list"
        :aria-busy="loading"
      >
        <article v-for="item in items" :key="item.id" class="admin-feedback-card">
          <header>
            <div class="feedback-card__identity">
              <el-tag :type="item.feedback === 'like' ? 'success' : 'danger'">
                {{ item.feedback === 'like' ? '有帮助' : '需改进' }}
              </el-tag>
              <span>{{ item.username || `用户 #${item.user_id}` }}</span>
            </div>
            <time :datetime="item.timestamp">{{ formatDate(item.timestamp) }}</time>
          </header>
          <p class="feedback-card__content">{{ item.content }}</p>
          <footer>
            <span>MSG #{{ item.id }}</span>
            <i aria-hidden="true"></i>
            <span>SESSION #{{ item.session_id }}</span>
          </footer>
        </article>
        <div v-if="!loading && !items.length" class="admin-empty feedback-empty">
          <span class="feedback-empty__orbit" aria-hidden="true"><i></i></span>
          <strong>没有匹配的反馈</strong>
          <p>当前筛选条件下没有反馈。</p>
        </div>
      </div>
      <p class="sr-only" aria-live="polite" aria-atomic="true">
        {{ loading ? '' : `已加载 ${items.length} 条反馈` }}
      </p>
      <el-pagination
        class="admin-pagination" background layout="prev, pager, next, total"
        :current-page="page" :page-size="pageSize" :total="total"
        @current-change="changePage"
      />
    </section>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getAdminFeedback, getErrorMessage } from '../../api'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filter = ref('')
const loading = ref(true)
const errorMessage = ref('')
const formatDate = (value) => value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'

const load = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await getAdminFeedback({ page: page.value, pageSize, feedback: filter.value })
    items.value = response.data.items || []
    total.value = response.data.total || 0
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '反馈列表加载失败。')
  } finally {
    loading.value = false
  }
}
const applyFilter = () => { page.value = 1; load() }
const changePage = (value) => { page.value = value; load() }
onMounted(load)
</script>

<style scoped>
.feedback-page {
  position: relative;
  isolation: isolate;
}

.feedback-page::before {
  position: absolute;
  z-index: -1;
  top: -8rem;
  left: -7rem;
  width: 22rem;
  height: 22rem;
  border: 1px solid var(--color-orbit);
  border-radius: 50%;
  background: radial-gradient(circle, var(--color-aurora-blue-soft), transparent 68%);
  content: '';
  pointer-events: none;
}

.feedback-panel {
  position: relative;
  overflow: hidden;
  padding: clamp(1.25rem, 3vw, 2rem);
  border-radius: var(--radius-panel);
  background:
    linear-gradient(145deg, var(--color-surface), var(--color-surface-subtle));
}

.feedback-panel::before {
  position: absolute;
  top: 0;
  left: 0;
  width: 11rem;
  height: 1px;
  background: var(--aurora-gradient);
  content: '';
}

.feedback-heading {
  position: relative;
  z-index: 1;
  align-items: flex-end;
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-border);
}

.feedback-heading__copy h2 {
  margin-top: var(--space-2);
  font-size: clamp(1.35rem, 2vw, 1.75rem);
  letter-spacing: -.025em;
}

.feedback-heading__copy > p:last-child {
  max-width: 38rem;
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-body);
}

.feedback-heading__controls {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.feedback-total {
  display: inline-flex;
  min-height: var(--control-height-large);
  align-items: center;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: var(--color-surface-glass);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  white-space: nowrap;
}

.feedback-page :deep(.el-radio-button__inner) {
  display: inline-flex;
  min-height: var(--control-height-large);
  align-items: center;
  justify-content: center;
  padding-inline: var(--space-4);
}

.feedback-page :deep(.el-radio-button__original-radio:focus-visible + .el-radio-button__inner) {
  position: relative;
  z-index: 1;
  box-shadow: var(--focus-ring-strong);
}

.feedback-page :deep(.el-button) {
  min-height: var(--control-height-large);
}

.feedback-page .admin-inline-error {
  position: relative;
  z-index: 1;
  margin-bottom: var(--space-5);
  padding: var(--space-4);
  border-radius: var(--radius-card);
}

.feedback-page .admin-inline-error > span strong,
.feedback-page .admin-inline-error > span small {
  display: block;
}

.feedback-page .admin-inline-error > span small {
  margin-top: var(--space-1);
  color: var(--color-text-secondary);
}

.feedback-list {
  position: relative;
  z-index: 1;
  gap: var(--space-4);
  min-height: 16rem;
}

.feedback-list :deep(.el-loading-mask) {
  border-radius: var(--radius-card);
  background: var(--color-surface-glass);
  backdrop-filter: blur(var(--glass-blur));
}

.feedback-list .admin-feedback-card {
  position: relative;
  padding: clamp(1rem, 2.5vw, 1.5rem);
  overflow: hidden;
  border-color: var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface-glass);
  box-shadow: none;
}

.feedback-list .admin-feedback-card::before {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 2px;
  background: var(--aurora-gradient);
  content: '';
  opacity: .72;
}

.feedback-list .admin-feedback-card header {
  gap: var(--space-4);
}

.feedback-card__identity {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-3);
}

.feedback-card__identity > span {
  overflow: hidden;
  color: var(--color-text-secondary);
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feedback-list .admin-feedback-card time {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
}

.feedback-card__content {
  margin: var(--space-5) 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-body-large);
  line-height: 1.75;
}

.feedback-list .admin-feedback-card footer {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-muted);
  letter-spacing: .035em;
}

.feedback-list .admin-feedback-card footer i {
  width: .25rem;
  height: .25rem;
  border-radius: 50%;
  background: var(--color-border-strong);
}

.feedback-empty {
  min-height: 18rem;
  align-content: center;
  padding: var(--space-8);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-card);
  background: var(--color-surface-glass);
  text-align: center;
}

.feedback-empty strong {
  margin-top: var(--space-5);
  color: var(--color-text-primary);
  font-size: var(--font-size-component-title);
}

.feedback-empty p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
}

.feedback-empty__orbit {
  position: relative;
  display: grid;
  width: 4.5rem;
  height: 4.5rem;
  place-items: center;
  border: 1px solid var(--color-orbit-strong);
  border-radius: 50%;
  background: var(--aurora-gradient-soft);
}

.feedback-empty__orbit::before {
  position: absolute;
  width: 2.5rem;
  height: 2.5rem;
  border: 1px solid var(--color-orbit-strong);
  border-radius: 50%;
  content: '';
}

.feedback-empty__orbit i {
  width: .5rem;
  height: .5rem;
  border-radius: 50%;
  background: var(--color-primary);
  box-shadow: 0 0 0 .3rem var(--color-primary-soft);
}

.feedback-page .admin-pagination {
  position: relative;
  z-index: 1;
  min-height: var(--control-height-large);
}

@media (max-width: 767px) {
  .feedback-page::before {
    left: -12rem;
  }

  .feedback-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .feedback-heading__controls {
    align-items: stretch;
    flex-direction: column;
  }

  .feedback-total {
    justify-content: center;
  }

  .feedback-heading__controls :deep(.el-radio-group) {
    display: flex;
    width: 100%;
  }

  .feedback-heading__controls :deep(.el-radio-button) {
    flex: 1 1 0;
  }

  .feedback-heading__controls :deep(.el-radio-button__inner) {
    width: 100%;
    padding-inline: var(--space-2);
  }

  .feedback-page .admin-inline-error {
    align-items: stretch;
    flex-direction: column;
  }

  .feedback-page .admin-inline-error :deep(.el-button) {
    width: 100%;
  }

  .feedback-list .admin-feedback-card header {
    align-items: flex-start;
    flex-direction: column;
    gap: var(--space-3);
  }

  .feedback-list .admin-feedback-card header time {
    margin-left: 0;
  }

  .feedback-card__identity {
    width: 100%;
  }

  .feedback-card__content {
    font-size: var(--font-size-body);
  }

  .feedback-page .admin-pagination {
    justify-content: center;
    overflow-x: auto;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .feedback-panel,
  .feedback-total,
  .feedback-list .admin-feedback-card,
  .feedback-empty {
    background: var(--color-surface);
  }

  .feedback-list :deep(.el-loading-mask) {
    background: var(--color-surface);
    backdrop-filter: none;
  }
}
</style>
