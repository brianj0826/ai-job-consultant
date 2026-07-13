<template>
  <section
    class="admin-page admin-directory-page"
    data-testid="admin-users-page"
    aria-labelledby="admin-users-title"
  >
    <section class="admin-panel admin-panel--command">
      <header class="admin-command">
        <div class="admin-command__intro">
          <p class="technical-label">IDENTITY &amp; ACCESS</p>
          <h2 id="admin-users-title">用户管理</h2>
          <p>维护账号角色与访问状态，受保护账号和高权限操作仍遵循既有安全策略。</p>
        </div>
        <div class="admin-command__signal" aria-label="用户记录总数">
          <span>USER INDEX</span>
          <strong class="tabular-nums">{{ loading ? '—' : total }}</strong>
          <small>条账号记录</small>
        </div>
      </header>

      <div class="admin-command__toolbar">
        <div>
          <p class="technical-label">ACCOUNT DIRECTORY</p>
          <p class="admin-command__hint">按用户名定位账号并执行授权操作</p>
        </div>
        <form class="admin-filter" role="search" @submit.prevent="applySearch">
          <el-input v-model="searchDraft" clearable placeholder="按用户名搜索" aria-label="按用户名搜索" />
          <el-button native-type="submit" type="primary">搜索</el-button>
        </form>
      </div>

      <div v-if="errorMessage" class="admin-inline-error" role="alert">
        <span>{{ errorMessage }}</span><el-button text @click="load">重试</el-button>
      </div>

      <div class="admin-table-shell" role="region" aria-label="用户账号列表" tabindex="0">
        <el-table v-loading="loading" :data="items" row-key="id" empty-text="没有匹配的用户">
          <el-table-column label="用户" min-width="180">
            <template #default="{ row }">
              <div class="admin-user-cell">
                <strong>{{ row.username }}</strong>
                <span class="admin-user-cell__meta">
                  <small>#{{ row.id }}</small>
                  <el-tag v-if="row.must_change_password" size="small" type="warning">需改密</el-tag>
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="角色" min-width="160">
            <template #default="{ row }">
              <el-select
                v-if="canChangeRole(row)"
                :model-value="row.role"
                :disabled="pendingUserId === row.id"
                :aria-label="`修改 ${row.username} 的用户角色`"
                @change="(role) => changeRole(row, role)"
              >
                <el-option label="普通用户" value="user" />
                <el-option label="管理员" value="admin" />
                <el-option label="超级管理员" value="super_admin" />
              </el-select>
              <el-tag v-else effect="plain">{{ roleLabel(row.role) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
                {{ row.status === 'active' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="session_count" label="会话" width="88" />
          <el-table-column prop="message_count" label="消息" width="88" />
          <el-table-column label="最近登录" min-width="170">
            <template #default="{ row }">{{ formatDate(row.last_login_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" min-width="240" fixed="right">
            <template #default="{ row }">
              <div class="admin-row-actions" role="group" :aria-label="`${row.username} 的账号操作`">
                <el-button
                  v-if="canChangeStatus(row)"
                  size="small"
                  :type="row.status === 'active' ? 'danger' : 'success'"
                  plain
                  :loading="pendingUserId === row.id"
                  @click="toggleStatus(row)"
                >
                  {{ row.status === 'active' ? '停用' : '启用' }}
                </el-button>
                <el-button
                  v-if="canResetPassword(row)"
                  size="small"
                  plain
                  :loading="pendingUserId === row.id"
                  @click="resetPassword(row)"
                >
                  重置密码
                </el-button>
                <span v-if="!canChangeStatus(row) && !canResetPassword(row)" class="admin-muted">受保护账号</span>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <el-pagination
        class="admin-pagination"
        background
        layout="prev, pager, next, total"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        @current-change="changePage"
      />
    </section>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAdminUsers,
  getErrorMessage,
  resetAdminUserPassword,
  updateAdminUserRole,
  updateAdminUserStatus
} from '../../api'
import { useAuth } from '../../composables/useAuth'

const { currentUser, isSuperAdmin } = useAuth()
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const search = ref('')
const searchDraft = ref('')
const loading = ref(true)
const errorMessage = ref('')
const pendingUserId = ref(null)

const replaceUser = (user) => {
  const index = items.value.findIndex((item) => item.id === user.id)
  if (index >= 0) items.value[index] = { ...items.value[index], ...user }
}

const roleLabel = (role) => ({ user: '普通用户', admin: '管理员', super_admin: '超级管理员' })[role] || role
const formatDate = (value) => value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '从未登录'
const canChangeRole = (row) => isSuperAdmin.value && row.id !== currentUser.value?.id
const canChangeStatus = (row) => row.id !== currentUser.value?.id && (row.role === 'user' || isSuperAdmin.value)
const canResetPassword = (row) => isSuperAdmin.value && row.id !== currentUser.value?.id

const load = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await getAdminUsers({ page: page.value, pageSize, search: search.value })
    items.value = response.data.items || []
    total.value = response.data.total || 0
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '用户列表加载失败。')
  } finally {
    loading.value = false
  }
}

const applySearch = () => {
  search.value = searchDraft.value.trim()
  page.value = 1
  load()
}

const changePage = (value) => {
  page.value = value
  load()
}

const toggleStatus = async (row) => {
  const nextStatus = row.status === 'active' ? 'disabled' : 'active'
  try {
    await ElMessageBox.confirm(
      nextStatus === 'disabled'
        ? `停用「${row.username}」会立即撤销其所有登录会话，是否继续？`
        : `确定重新启用「${row.username}」吗？`,
      nextStatus === 'disabled' ? '停用账号' : '启用账号',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
    )
    pendingUserId.value = row.id
    const response = await updateAdminUserStatus(row.id, nextStatus)
    replaceUser(response.data.user)
    ElMessage.success('账号状态已更新')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(getErrorMessage(error, '账号状态更新失败。'))
  } finally {
    pendingUserId.value = null
  }
}

const changeRole = async (row, role) => {
  if (role === row.role) return
  try {
    await ElMessageBox.confirm(`确定将「${row.username}」设为“${roleLabel(role)}”吗？`, '修改角色', {
      type: 'warning', confirmButtonText: '确认修改', cancelButtonText: '取消'
    })
    pendingUserId.value = row.id
    const response = await updateAdminUserRole(row.id, role)
    replaceUser(response.data.user)
    ElMessage.success('用户角色已更新')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(getErrorMessage(error, '角色更新失败。'))
  } finally {
    pendingUserId.value = null
  }
}

const resetPassword = async (row) => {
  try {
    await ElMessageBox.confirm(
      `将为「${row.username}」生成一次性临时密码、撤销其登录会话，并要求下次登录后改密。是否继续？`,
      '重置用户密码',
      { type: 'warning', confirmButtonText: '生成临时密码', cancelButtonText: '取消' }
    )
    pendingUserId.value = row.id
    const response = await resetAdminUserPassword(row.id)
    replaceUser(response.data.user)
    await ElMessageBox.alert(response.data.temporary_password, '临时密码（仅显示一次）', {
      confirmButtonText: '我已安全保存',
      type: 'warning',
      dangerouslyUseHTMLString: false
    })
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(getErrorMessage(error, '密码重置失败。'))
  } finally {
    pendingUserId.value = null
  }
}

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
  inset: -9rem -7rem auto auto;
  width: 24rem;
  height: 24rem;
  border: 1px solid var(--color-orbit);
  border-radius: 50%;
  background: none;
  box-shadow: 0 0 0 4rem var(--color-aurora-blue-soft), 0 0 0 8rem var(--color-aurora-violet-soft);
  content: '';
  opacity: .5;
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
  background: linear-gradient(118deg, var(--color-surface-elevated), var(--color-aurora-violet-soft));
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

.admin-user-cell {
  display: grid;
  gap: var(--space-1);
}

.admin-user-cell__meta {
  display: flex;
  min-height: 1.5rem;
  align-items: center;
  gap: var(--space-2);
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
    min-width: 66rem;
  }

  .admin-table-shell :deep(.el-table-fixed-column--right) {
    right: auto !important;
    position: static !important;
    box-shadow: none !important;
  }

  .admin-row-actions :deep(.el-button) {
    min-height: 2.75rem;
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
