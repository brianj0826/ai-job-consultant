<template>
  <section class="admin-page" data-testid="admin-feedback-page">
    <section class="admin-panel">
      <div class="admin-panel__heading admin-panel__heading--wrap">
        <div><p class="technical-label">QUALITY REVIEW</p><h2>反馈审阅</h2></div>
        <el-radio-group v-model="filter" @change="applyFilter">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="like">有帮助</el-radio-button>
          <el-radio-button value="dislike">需改进</el-radio-button>
        </el-radio-group>
      </div>
      <div v-if="errorMessage" class="admin-inline-error" role="alert">
        <span>{{ errorMessage }}</span><el-button text @click="load">重试</el-button>
      </div>
      <div v-loading="loading" class="admin-feedback-list">
        <article v-for="item in items" :key="item.id" class="admin-feedback-card">
          <header>
            <el-tag :type="item.feedback === 'like' ? 'success' : 'danger'">
              {{ item.feedback === 'like' ? '有帮助' : '需改进' }}
            </el-tag>
            <span>{{ item.username || `用户 #${item.user_id}` }}</span>
            <time :datetime="item.timestamp">{{ formatDate(item.timestamp) }}</time>
          </header>
          <p>{{ item.content }}</p>
          <footer>消息 #{{ item.id }} · 会话 #{{ item.session_id }}</footer>
        </article>
        <div v-if="!loading && !items.length" class="admin-empty">当前筛选条件下没有反馈。</div>
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
