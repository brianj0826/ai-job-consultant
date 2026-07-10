<template>
  <el-drawer
    title="📊 数据分析"
    v-model="visible"
    direction="rtl"
    size="420px"
    @open="loadData"
  >
    <!-- 加载中 -->
    <div v-if="loading" style="text-align:center;padding:40px">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载数据中...</p>
    </div>

    <!-- 数据展示 -->
    <div v-else>
      <!-- 1. 概览卡片 -->
      <h3 style="margin:0 0 12px">📋 求职进度</h3>
      <div class="stat-cards">
        <div class="stat-card stat-blue">
          <div class="stat-num">{{ overview.total_sessions }}</div>
          <div class="stat-label">总对话数</div>
        </div>
        <div class="stat-card stat-green">
          <div class="stat-num">{{ overview.total_messages }}</div>
          <div class="stat-label">消息数</div>
        </div>
        <div class="stat-card stat-purple">
          <div class="stat-num">{{ resumeCount }}</div>
          <div class="stat-label">简历数</div>
        </div>
      </div>
      <p style="font-size:13px;color:#909399;text-align:center;margin:8px 0">
        💡 提示：完整对话轮次越多，AI 对简历的理解越深
      </p>

      <el-divider />

      <!-- 2. 反馈统计 -->
      <h3 style="margin:0 0 12px">👍 反馈统计</h3>
      <div v-if="feedback.total_rated > 0">
        <div class="feedback-row">
          <span>👍 满意</span>
          <span class="feedback-num">{{ feedback.likes }}</span>
        </div>
        <el-progress
          :percentage="feedback.like_rate"
          :color="'#67C23A'"
          :stroke-width="16"
          style="margin-bottom:8px"
        />
        <div class="feedback-row">
          <span>👎 不满意</span>
          <span class="feedback-num">{{ feedback.dislikes }}</span>
        </div>
        <el-progress
          :percentage="100 - feedback.like_rate"
          :color="'#F56C6C'"
          :stroke-width="16"
        />
        <p style="color:#999;font-size:13px;margin-top:8px">
          共 {{ feedback.total_rated }} 条评价，满意度 {{ feedback.like_rate }}%
        </p>
      </div>
      <div v-else style="color:#999;text-align:center;padding:20px">
        暂无反馈数据
      </div>

      <el-divider />

      <!-- 3. 每日趋势 -->
      <h3 style="margin:0 0 12px">📈 近7天消息趋势</h3>
      <div v-if="trend.length" class="trend-chart">
        <div
          v-for="item in trend"
          :key="item.date"
          class="trend-bar-wrap"
        >
          <div class="trend-val">{{ item.count }}</div>
          <div
            class="trend-bar"
            :style="{ height: barHeight(item.count) + 'px' }"
          ></div>
          <div class="trend-date">{{ formatDate(item.date) }}</div>
        </div>
      </div>
      <div v-else style="color:#999;text-align:center;padding:20px">
        暂无数据
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import {
  getAnalyticsOverview,
  getAnalyticsFeedback,
  getAnalyticsTrend
} from '../api'

const props = defineProps({
  userId: Number
})

const visible = ref(false)
const loading = ref(false)

const overview = ref({ total_sessions: 0, total_messages: 0, avg_per_session: 0 })
const feedback = ref({ likes: 0, dislikes: 0, no_feedback: 0, total_rated: 0, like_rate: 0 })
const trend = ref([])
const resumeCount = ref(0)

const maxCount = computed(() => {
  if (!trend.value.length) return 1
  return Math.max(...trend.value.map(t => t.count), 1)
})

const barHeight = (count) => {
  return Math.max(count / maxCount.value * 120, 4)
}

const formatDate = (dateStr) => {
  // dateStr is like "2026-06-26"
  const parts = dateStr.split('-')
  return parts[1] + '/' + parts[2]
}

const loadData = async () => {
  loading.value = true
  try {
    const uid = props.userId
    const [ov, fb, tr] = await Promise.all([
      getAnalyticsOverview(uid),
      getAnalyticsFeedback(uid),
      getAnalyticsTrend(uid, 7)
    ])
    overview.value = ov.data
    feedback.value = fb.data
    trend.value = tr.data
    // 获取简历数量
    try {
      const { getDocStatus } = await import('../api')
      const docRes = await getDocStatus(uid)
      resumeCount.value = (docRes.data.sources || []).filter(s => s.type === 'file').length
    } catch { resumeCount.value = 0 }
  } catch (e) {
    console.error('加载分析数据失败:', e)
  } finally {
    loading.value = false
  }
}

const open = () => {
  visible.value = true
}

const close = () => {
  visible.value = false
}

defineExpose({ open, close })
</script>

<style scoped>
.stat-cards {
  display: flex;
  gap: 12px;
}
.stat-card {
  flex: 1;
  text-align: center;
  padding: 16px 8px;
  background: #f5f7fa;
  border-radius: 8px;
}
.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: #409EFF;
}
.stat-blue .stat-num { color: #409EFF; }
.stat-green .stat-num { color: #67C23A; }
.stat-purple .stat-num { color: #9b59b6; }
.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
.feedback-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  font-size: 14px;
}
.feedback-num {
  font-weight: 600;
  color: #606266;
}
.trend-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 180px;
  padding: 0 4px;
}
.trend-bar-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}
.trend-val {
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
}
.trend-bar {
  width: 28px;
  background: linear-gradient(to top, #409EFF, #79bbff);
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: height 0.4s ease;
}
.trend-date {
  font-size: 11px;
  color: #909399;
  margin-top: 6px;
}
</style>
