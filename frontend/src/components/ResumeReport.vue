<template>
  <el-drawer v-model="visible" title="📋 简历分析报告" direction="rtl" size="480px" @open="initChart">
    <div v-if="!reportText" style="text-align:center;color:#999;padding:40px">暂无分析数据，请先上传简历并点击「分析简历」</div>
    <div v-else class="report-body">
      <!-- 总分 -->
      <div class="score-ring">
        <div class="ring-chart" ref="chartRef"></div>
        <div class="score-info">
          <div class="score-num">{{ score }}</div>
          <div class="score-label">综合评分</div>
        </div>
      </div>
      <!-- 分析内容 -->
      <div class="report-text" v-html="renderedReport"></div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, nextTick, computed } from 'vue'
import { marked } from 'marked'
// echarts 通过 index.html CDN 全局加载

const props = defineProps({ reportText: { type: String, default: '' } })
const visible = ref(false)
const chartRef = ref(null)

// 从报告文本中提取评分
const score = computed(() => {
  const m = props.reportText.match(/(\d+)\s*分/)
  return m ? m[1] : '—'
})

// 渲染报告文本为 HTML（使用 marked 库）
const renderedReport = computed(() => {
  if (!props.reportText) return ''
  return marked(props.reportText)
})

const open = () => { visible.value = true }
const close = () => { visible.value = false }

const initChart = () => {
  nextTick(() => {
    if (!chartRef.value) return
    const chart = window.echarts.init(chartRef.value)
    chart.setOption({
      radar: {
        center: ['50%', '50%'],
        radius: '70%',
        indicator: [
          { name: '项目经验', max: 100 },
          { name: '技术栈', max: 100 },
          { name: '学历匹配', max: 100 },
          { name: '成果量化', max: 100 },
          { name: '格式规范', max: 100 },
        ],
        axisName: { color: '#666', fontSize: 10 },
      },
      series: [{
        type: 'radar',
        data: [{ value: [score.value * 10 || 65, score.value * 11 || 58, 70, score.value * 7 || 42, 80], name: '当前简历' }],
        areaStyle: { color: 'rgba(91,127,255,0.25)' },
        lineStyle: { color: '#5b7fff', width: 2 },
        itemStyle: { color: '#5b7fff' },
      }],
    })
  })
}

defineExpose({ open, close })
</script>

<style scoped>
.report-body { padding: 8px 0; }
.score-ring {
  display: flex; align-items: center; gap: 16px;
  padding: 16px; background: #f8f9fd; border-radius: 14px; margin-bottom: 20px;
}
.ring-chart { width: 140px; height: 140px; }
.score-info { text-align: center; }
.score-num { font-size: 40px; font-weight: 800; color: #5b7fff; line-height: 1.1; }
.score-label { font-size: 13px; color: #909399; margin-top: 4px; }
.report-text { line-height: 1.8; font-size: 14px; color: #444; }
.report-text :deep(strong) { color: #5b7fff; }
</style>
