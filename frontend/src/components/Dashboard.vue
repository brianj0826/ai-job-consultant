<template>
  <div class="dashboard">
    <!-- 欢迎区 -->
    <div class="welcome-header">
      <h1 class="greeting">👋 欢迎回来，{{ username }}</h1>
      <p class="subtitle">今天想提升哪方面的求职竞争力？</p>
    </div>

    <!-- 三个核心功能卡片 -->
    <div class="card-grid">
      <div class="feature-card card-resume" @click="$emit('action', '分析简历')">
        <div class="card-icon">📋</div>
        <h3>简历智能分析</h3>
        <p>上传简历，AI 从技术栈、项目经验、成果量化等维度深度分析，给出评分与改进建议</p>
        <span class="card-action">开始分析 →</span>
      </div>

      <div class="feature-card card-match" @click="$emit('action', '匹配')">
        <div class="card-icon">🎯</div>
        <h3>岗位精准匹配</h3>
        <p>输入目标岗位 JD，AI 对比你的简历与岗位要求，量化匹配度并指出技能差距</p>
        <span class="card-action">开始匹配 →</span>
      </div>

      <div class="feature-card card-interview" @click="$emit('action', '模拟面试')">
        <div class="card-icon">🎤</div>
        <h3>模拟面试训练</h3>
        <p>AI 扮演面试官，针对目标岗位出题，评估你的回答质量并给出专业反馈</p>
        <span class="card-action">开始练习 →</span>
      </div>
    </div>

    <!-- 求职小贴士 -->
    <div class="tips-section">
      <h3 class="tips-title">💡 求职小贴士</h3>
      <div class="tips-grid">
        <div class="tip-item">
          <span class="tip-num">01</span>
          <div>
            <strong>STAR 法则让你的简历脱颖而出</strong>
            <p>Situation（情境）→ Task（任务）→ Action（行动）→ Result（结果）。不要只写"负责开发XX系统"，改成"主导开发XX系统，优化核心查询逻辑，将接口响应时间从800ms降至120ms，日均服务用户10万+"。用具体数字量化成果，让HR一眼看到你的价值。简历不是记流水账，而是展示你解决过的真实难题。</p>
          </div>
        </div>
        <div class="tip-item">
          <span class="tip-num">02</span>
          <div>
            <strong>投递前先做"岗位拆解"</strong>
            <p>拿到一份JD不要立刻投递，先逐条拆解：哪些是硬性要求（学历/年限/技能），哪些是加分项（行业经验/开源贡献），哪些是软性要求（沟通/团队协作）。对照自己的简历，标注出每条要求的匹配程度。对于明显不达标的硬性要求，优先补齐再投递，避免盲目海投浪费机会。</p>
          </div>
        </div>
        <div class="tip-item">
          <span class="tip-num">03</span>
          <div>
            <strong>面试本质是"讲故事"</strong>
            <p>每段项目经历准备一个3分钟的精简版本：背景是什么？你承担什么角色？遇到了什么困难？你做了哪些关键决策？最终实现了什么效果？用"问题→方案→结果"的结构串联。面试官不是考你背诵，而是看你解决问题的思路。提前准备好2-3个有深度的反问，展现你对公司和岗位的真正兴趣。</p>
          </div>
        </div>
        <div class="tip-item">
          <span class="tip-num">04</span>
          <div>
            <strong>持续迭代比一次完美更重要</strong>
            <p>很多求职者花几周打磨一份"完美简历"才敢投递，但最好的策略是小步快跑：先投3-5家意向较低的公司试试反应，根据反馈快速调整简历和面试策略。每轮面试后总结经验，优化不足。数据显示，求职者平均面试7-8次后才能进入最佳状态，越早开始真实演练，越早找到节奏。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  username: { type: String, default: '同学' }
})
defineEmits(['action'])
</script>

<style scoped>
.dashboard {
  max-width: 800px;
  margin: 0 auto;
  padding: 36px 32px;
  height: 100%;
  overflow-y: auto;
}
.dashboard::-webkit-scrollbar { width: 5px; }
.dashboard::-webkit-scrollbar-thumb { background: #d0d5e0; border-radius: 3px; }

/* 欢迎区 */
.welcome-header {
  margin-bottom: 32px;
}
.greeting {
  font-size: 26px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0 0 6px;
}
.subtitle {
  font-size: 15px;
  color: #909399;
  margin: 0;
}

/* 功能卡片 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  margin-bottom: 36px;
}
.feature-card {
  background: #fff;
  border-radius: 14px;
  padding: 24px 20px;
  cursor: pointer;
  transition: all 0.25s ease;
  border: 1.5px solid #eef0f6;
  position: relative;
  overflow: hidden;
}
.feature-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 3px;
  border-radius: 14px 14px 0 0;
}
.card-resume::before { background: linear-gradient(90deg, #667eea, #764ba2); }
.card-match::before { background: linear-gradient(90deg, #f093fb, #f5576c); }
.card-interview::before { background: linear-gradient(90deg, #4facfe, #00f2fe); }

.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 28px rgba(0,0,0,0.08);
}
.card-icon { font-size: 32px; margin-bottom: 10px; }
.feature-card h3 {
  font-size: 16px; font-weight: 600; color: #2c3e50; margin: 0 0 8px;
}
.feature-card p {
  font-size: 13px; color: #909399; line-height: 1.6; margin: 0 0 14px;
}
.card-action {
  font-size: 13px; font-weight: 600; color: #5b7fff;
}

/* 小贴士 */
.tips-section {
  background: #fff;
  border-radius: 14px;
  padding: 22px 24px;
  border: 1.5px solid #eef0f6;
}
.tips-title {
  font-size: 16px; font-weight: 600; color: #2c3e50;
  margin: 0 0 16px;
}
.tips-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.tip-item {
  display: flex; gap: 12px; align-items: flex-start;
  padding: 12px 14px;
  background: #f8f9fd;
  border-radius: 10px;
}
.tip-num {
  font-size: 22px; font-weight: 800; color: #d0d5e0;
  flex-shrink: 0; line-height: 1;
}
.tip-item strong {
  font-size: 13px; color: #444; display: block; margin-bottom: 4px;
}
.tip-item p {
  font-size: 12px; color: #909399; margin: 0; line-height: 1.6;
}
</style>
