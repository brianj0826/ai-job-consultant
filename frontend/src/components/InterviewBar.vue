<template>
  <div v-if="active" class="interview-bar">
    <div class="bar-left">
      <span class="bar-icon">🎤</span>
      <span class="bar-label">模拟面试中</span>
      <el-divider direction="vertical" />
      <span class="bar-progress">第 {{ current }} / {{ total }} 题</span>
      <el-progress :percentage="Math.round(current/total*100)" :stroke-width="6" :show-text="false" style="width:100px" />
    </div>
    <div class="bar-right">
      <el-button @click="$emit('end')" size="small" type="danger" plain>结束面试</el-button>
      <el-button @click="$emit('score')" size="small" type="primary">查看评分</el-button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  active: { type: Boolean, default: false },
  current: { type: Number, default: 1 },
  total: { type: Number, default: 5 },
})
defineEmits(['end', 'score'])
</script>

<style scoped>
.interview-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 20px;
  background: linear-gradient(135deg, #f8f0ff, #f0f4ff);
  border-bottom: 1.5px solid #e8e0f0;
  flex-shrink: 0;
}
.bar-left { display: flex; align-items: center; gap: 10px; }
.bar-icon { font-size: 18px; }
.bar-label { font-weight: 600; font-size: 14px; color: #6c5ce7; }
.bar-progress { font-size: 13px; color: #666; }
.bar-right { display: flex; gap: 8px; }
</style>
