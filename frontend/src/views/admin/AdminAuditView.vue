<template>
  <section class="admin-page" data-testid="admin-audit-page">
    <section class="admin-panel">
      <div class="admin-panel__heading admin-panel__heading--wrap">
        <div><p class="technical-label">PRIVILEGED ACTIVITY</p><h2>审计日志</h2></div>
        <form class="admin-filter" @submit.prevent="applyFilter">
          <el-input v-model="actionDraft" clearable placeholder="按操作标识筛选" aria-label="按操作标识筛选" />
          <el-button native-type="submit" type="primary">筛选</el-button>
        </form>
      </div>
      <div v-if="errorMessage" class="admin-inline-error" role="alert">
        <span>{{ errorMessage }}</span><el-button text @click="load">重试</el-button>
      </div>
      <el-table v-loading="loading" :data="items" row-key="id" empty-text="暂无审计记录">
        <el-table-column prop="id" label="#" width="70" />
        <el-table-column label="管理员" min-width="140">
          <template #default="{ row }">{{ row.admin_username || `#${row.admin_user_id}` }}</template>
        </el-table-column>
        <el-table-column prop="action" label="操作" min-width="190" />
        <el-table-column label="目标" min-width="140">
          <template #default="{ row }">{{ row.target_type }} · {{ row.target_id || '—' }}</template>
        </el-table-column>
        <el-table-column label="详情" min-width="260">
          <template #default="{ row }"><code class="admin-audit-details">{{ details(row.details) }}</code></template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP" min-width="130" />
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
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
