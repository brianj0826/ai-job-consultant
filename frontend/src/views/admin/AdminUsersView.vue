<template>
  <section class="admin-page" data-testid="admin-users-page">
    <section class="admin-panel">
      <div class="admin-panel__heading admin-panel__heading--wrap">
        <div><p class="technical-label">IDENTITY & ACCESS</p><h2>用户管理</h2></div>
        <form class="admin-filter" role="search" @submit.prevent="applySearch">
          <el-input v-model="searchDraft" clearable placeholder="按用户名搜索" aria-label="按用户名搜索" />
          <el-button native-type="submit" type="primary">搜索</el-button>
        </form>
      </div>

      <div v-if="errorMessage" class="admin-inline-error" role="alert">
        <span>{{ errorMessage }}</span><el-button text @click="load">重试</el-button>
      </div>

      <el-table v-loading="loading" :data="items" row-key="id" empty-text="没有匹配的用户">
        <el-table-column label="用户" min-width="170">
          <template #default="{ row }">
            <div class="admin-user-cell">
              <strong>{{ row.username }}</strong>
              <small>#{{ row.id }}</small>
              <el-tag v-if="row.must_change_password" size="small" type="warning">需改密</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" min-width="150">
          <template #default="{ row }">
            <el-select
              v-if="canChangeRole(row)"
              :model-value="row.role"
              :disabled="pendingUserId === row.id"
              aria-label="修改用户角色"
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
        <el-table-column prop="session_count" label="会话" width="80" />
        <el-table-column prop="message_count" label="消息" width="80" />
        <el-table-column label="最近登录" min-width="150">
          <template #default="{ row }">{{ formatDate(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="240" fixed="right">
          <template #default="{ row }">
            <div class="admin-row-actions">
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
