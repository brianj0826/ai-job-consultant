<template>
  <section
    class="admin-page admin-audit-page"
    data-testid="admin-audit-page"
    aria-labelledby="admin-audit-title"
  >
    <section class="admin-panel admin-panel--command">
      <header class="admin-command">
        <div class="admin-command__intro">
          <p class="technical-label">PRIVILEGED ACTIVITY</p>
          <h2 id="admin-audit-title">审计日志</h2>
          <p>追踪高权限操作、目标资源与访问来源，保留每条记录的原始详情。</p>
        </div>
        <div class="admin-command__signal" aria-label="审计记录总数">
          <span>EVENT LEDGER</span>
          <strong class="tabular-nums">{{ loading ? '—' : total }}</strong>
          <small>条审计记录</small>
        </div>
      </header>

      <div class="admin-command__toolbar">
        <div>
          <p class="technical-label">EVENT STREAM</p>
          <p class="admin-command__hint">使用完整操作标识收窄当前日志范围</p>
        </div>
        <form class="admin-filter" role="search" @submit.prevent="applyFilter">
          <el-input v-model="actionDraft" clearable placeholder="按操作标识筛选" aria-label="按操作标识筛选" />
          <el-button native-type="submit" type="primary">筛选</el-button>
        </form>
      </div>
      <div v-if="errorMessage" class="admin-inline-error" role="alert">
        <span>{{ errorMessage }}</span><el-button text @click="load">重试</el-button>
      </div>
      <div class="admin-table-shell" role="region" aria-label="高权限操作审计记录" tabindex="0">
        <el-table v-loading="loading" :data="items" row-key="id" empty-text="暂无审计记录">
          <el-table-column prop="id" label="#" width="76" />
          <el-table-column label="管理员" min-width="150">
            <template #default="{ row }">
              <strong class="admin-actor">{{ row.admin_username || `#${row.admin_user_id}` }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="210">
            <template #default="{ row }"><code class="admin-action-code">{{ row.action }}</code></template>
          </el-table-column>
          <el-table-column label="目标" min-width="160">
            <template #default="{ row }">
              <span class="admin-target"><strong>{{ row.target_type }}</strong><small>{{ row.target_id ?? '—' }}</small></span>
            </template>
          </el-table-column>
          <el-table-column label="详情" min-width="340">
            <template #default="{ row }"><code class="admin-audit-details">{{ details(row.details) }}</code></template>
          </el-table-column>
          <el-table-column prop="ip_address" label="IP" min-width="140" />
          <el-table-column label="时间" min-width="180">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </div>
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
import { getAdminAuditLogs, getErrorMessage } from '../../api'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const action = ref('')
const actionDraft = ref('')
const loading = ref(true)
const errorMessage = ref('')
const details = (value) => typeof value === 'string' ? value : JSON.stringify(value || {})
const formatDate = (value) => value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'

const load = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await getAdminAuditLogs({ page: page.value, pageSize, action: action.value })
    items.value = response.data.items || []
    total.value = response.data.total || 0
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '审计日志加载失败。')
  } finally {
    loading.value = false
  }
}
const applyFilter = () => { action.value = actionDraft.value.trim(); page.value = 1; load() }
const changePage = (value) => { page.value = value; load() }
onMounted(load)
</script>

<style scoped>
.admin-panel--command {
  position: relative;
  overflow: hidden;
  padding: 0;
  isolation: isolate;
}

.admin-panel--command::before {
  position: absolute;
  z-index: -1;
  inset: -11rem -8rem auto auto;
  width: 27rem;
  height: 27rem;
  border: 1px solid var(--color-orbit);
  border-radius: 50%;
  background: none;
  box-shadow: 0 0 0 4rem var(--color-aurora-cyan-soft), 0 0 0 8rem var(--color-aurora-blue-soft);
  content: '';
  opacity: .55;
  pointer-events: none;
}

.admin-command {
  display: flex;
  min-height: 11.5rem;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-8);
  padding: var(--space-8);
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(118deg, var(--color-surface-elevated), var(--color-aurora-blue-soft));
}

.admin-command__intro {
  max-width: 42rem;
}

.admin-command__intro h2 {
  margin: var(--space-2) 0 var(--space-3);
  font-size: clamp(1.65rem, 3vw, 2.35rem);
  line-height: 1.15;
}

.admin-command__intro > p:last-child,
.admin-command__hint {
  margin: 0;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.admin-command__signal {
  display: grid;
  min-width: 9rem;
  gap: var(--space-1);
  padding: var(--space-4) var(--space-5);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-card);
  background: var(--color-surface-glass);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(var(--glass-blur));
}

.admin-command__signal span,
.admin-command__signal small {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  letter-spacing: .06em;
}

.admin-command__signal strong {
  font-size: 1.75rem;
}

.admin-command__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-5);
  padding: var(--space-5) var(--space-8);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-subtle);
}

.admin-command__hint {
  margin-top: var(--space-1);
  font-size: var(--font-size-caption);
}

.admin-filter :deep(.el-input__wrapper),
.admin-filter :deep(.el-button) {
  min-height: 2.75rem;
}

.admin-inline-error {
  margin: var(--space-5) var(--space-8) 0;
}

.admin-table-shell {
  margin: var(--space-6) var(--space-8) 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface);
}

.admin-table-shell:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.admin-actor {
  color: var(--color-text-primary);
}

.admin-action-code {
  color: var(--color-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  font-weight: 700;
  overflow-wrap: anywhere;
}

.admin-target {
  display: grid;
  gap: var(--space-1);
}

.admin-target small {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.admin-audit-details {
  max-width: 32rem;
  max-height: 8.5rem;
  overflow: auto;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
  color: var(--color-text-secondary);
  line-height: 1.55;
  overflow-wrap: anywhere;
  text-overflow: clip;
  white-space: pre-wrap;
  word-break: break-word;
}

.admin-pagination {
  padding: 0 var(--space-8) var(--space-6);
}

@media (max-width: 767px) {
  .admin-command {
    min-height: 0;
    align-items: stretch;
    flex-direction: column;
    gap: var(--space-5);
    padding: var(--space-6) var(--space-4);
  }

  .admin-command__signal {
    grid-template-columns: 1fr auto;
    min-width: 0;
    align-items: center;
  }

  .admin-command__signal strong {
    grid-row: span 2;
    font-size: 1.5rem;
  }

  .admin-command__toolbar {
    align-items: stretch;
    flex-direction: column;
    padding: var(--space-4);
  }

  .admin-filter {
    align-items: stretch;
  }

  .admin-filter :deep(.el-input) {
    min-width: 0;
  }

  .admin-inline-error {
    margin: var(--space-4) var(--space-4) 0;
  }

  .admin-table-shell {
    margin: var(--space-4) var(--space-4) 0;
    overflow-x: auto;
  }

  .admin-table-shell :deep(.el-table) {
    min-width: 76rem;
  }

  .admin-pagination {
    justify-content: flex-start;
    overflow-x: auto;
    padding: 0 var(--space-4) var(--space-5);
  }

  .admin-pagination :deep(.btn-prev),
  .admin-pagination :deep(.btn-next),
  .admin-pagination :deep(.el-pager li) {
    min-width: 2.75rem;
    min-height: 2.75rem;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .admin-command__signal {
    background: var(--color-surface-elevated);
    backdrop-filter: none;
  }
}
</style>
