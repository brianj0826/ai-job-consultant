<template>
  <el-drawer v-model="visible" title="🎯 岗位匹配分析" direction="rtl" size="460px">
    <div v-if="!reportText" style="text-align:center;color:#999;padding:40px">暂无匹配数据，请先粘贴JD并点击「匹配」</div>
    <div v-else class="match-body">
      <!-- 匹配度 -->
      <div class="match-gauge">
        <el-progress type="dashboard" :percentage="matchPercent" :color="gaugeColor" :stroke-width="14" :width="160">
          <template #default="{ percentage }">
            <span class="gauge-num">{{ percentage }}%</span>
          </template>
        </el-progress>
        <div class="gauge-label">综合匹配度</div>
      </div>
      <!-- 技能对比 -->
      <div class="compare-section">
        <div class="compare-col">
          <div class="col-title">✅ 匹配技能</div>
          <el-tag v-for="(s,i) in matchedSkills" :key="i" type="success" effect="plain" size="small" style="margin:3px">{{ s }}</el-tag>
          <div v-if="!matchedSkills.length" class="empty-hint">等待分析…</div>
        </div>
        <div class="compare-col">
          <div class="col-title">⚠️ 缺失技能</div>
          <el-tag v-for="(s,i) in missingSkills" :key="i" type="danger" effect="plain" size="small" style="margin:3px">{{ s }}</el-tag>
          <div v-if="!missingSkills.length" class="empty-hint">等待分析…</div>
        </div>
      </div>
      <el-divider />
      <!-- 完整报告文字 -->
      <div class="report-text" v-html="renderedReport"></div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({ reportText: { type: String, default: '' } })
const visible = ref(false)

const matchPercent = computed(() => {
  const m = props.reportText.match(/匹配度[：:]\s*(\d+)/i) || props.reportText.match(/(\d+)\s*%/)
  return m ? parseInt(m[1]) : 50
})

const gaugeColor = computed(() => {
  if (matchPercent.value >= 70) return [{ color: '#67C23A', offset: 0 }, { color: '#67C23A', offset: 100 }]
  if (matchPercent.value >= 40) return [{ color: '#E6A23C', offset: 0 }, { color: '#E6A23C', offset: 100 }]
  return [{ color: '#F56C6C', offset: 0 }, { color: '#F56C6C', offset: 100 }]
})

const matchedSkills = computed(() => {
  const text = props.reportText
  const items = []
  const section = text.match(/匹配的技能[：:]([\s\S]*?)(?=缺失|加分|建议|$)/i)
  if (section) {
    const matches = section[1].matchAll(/[-•\d.]+\s*(.+)/g)
    for (const m of matches) items.push(m[1].trim().slice(0, 25))
  }
  return items.slice(0, 5)
})

const missingSkills = computed(() => {
  const text = props.reportText
  const items = []
  const section = text.match(/缺失的技能[：:]([\s\S]*?)(?=加分|建议|$)/i)
  if (section) {
    const matches = section[1].matchAll(/[-•\d.]+\s*(.+)/g)
    for (const m of matches) items.push(m[1].trim().slice(0, 25))
  }
  return items.slice(0, 5)
})

const renderedReport = computed(() => {
  if (!props.reportText) return ''
  return marked(props.reportText)
})

const open = () => { visible.value = true }
const close = () => { visible.value = false }

defineExpose({ open, close })
</script>

<style scoped>
.match-body { padding: 8px 0; }
.match-gauge { text-align: center; margin-bottom: 20px; }
.gauge-num { font-size: 28px; font-weight: 700; color: #5b7fff; }
.gauge-label { font-size: 13px; color: #909399; margin-top: -4px; }
.compare-section { display: flex; gap: 12px; margin-bottom: 12px; }
.compare-col { flex: 1; padding: 12px; background: #f8f9fd; border-radius: 10px; min-height: 80px; }
.col-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: #444; }
.empty-hint { font-size: 12px; color: #ccc; text-align: center; padding: 12px; }
.report-text { line-height: 1.8; font-size: 14px; color: #444; }
.report-text :deep(strong) { color: #5b7fff; }
</style>
