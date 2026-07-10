<template>
  <section class="dashboard" aria-labelledby="dashboard-title">
    <header class="dashboard-header">
      <p class="dashboard-kicker">CAREER COMMAND</p>
      <h1 id="dashboard-title" class="dashboard-title">欢迎回来，{{ username }}</h1>
      <p class="dashboard-subtitle">选择一个明确的下一步，让准备工作保持在可推进的节奏中。</p>
    </header>

    <div class="command-layout">
      <article class="command-spotlight" aria-labelledby="spotlight-title">
        <div class="spotlight-content">
          <p class="spotlight-kicker">
            <el-icon aria-hidden="true"><Lightning /></el-icon>
            NEXT BEST STEP
          </p>
          <h2 id="spotlight-title">从你的简历开始，建立更清晰的求职策略。</h2>
          <p>
            先梳理已有经历的表达、重点与可改进处，再把下一次投递和面试准备落到具体行动上。
          </p>
          <div class="spotlight-footer">
            <el-button class="spotlight-action" type="primary" @click="triggerAction('分析简历')">
              <el-icon aria-hidden="true"><DocumentChecked /></el-icon>
              分析简历
              <el-icon aria-hidden="true"><ArrowRight /></el-icon>
            </el-button>
            <span>上传简历后即可开始分析。</span>
          </div>
        </div>
        <div class="spotlight-orbit" aria-hidden="true">
          <span class="orbit-ring orbit-ring--outer"></span>
          <span class="orbit-ring orbit-ring--inner"></span>
          <span class="orbit-core"><el-icon><DocumentChecked /></el-icon></span>
        </div>
      </article>

      <section class="quick-launch" aria-labelledby="quick-launch-title">
        <div class="quick-launch-heading">
          <p id="quick-launch-title" class="section-kicker">CONTINUE WITH</p>
          <p>选择你的下一项训练</p>
        </div>

        <button class="task-card" type="button" @click="triggerAction('匹配')">
          <span class="task-icon" aria-hidden="true"><el-icon><Aim /></el-icon></span>
          <span class="task-copy">
            <strong>岗位精准匹配</strong>
            <small>对照目标 JD，梳理匹配项与待补齐方向。</small>
          </span>
          <el-icon class="task-arrow" aria-hidden="true"><ArrowRight /></el-icon>
        </button>

        <button class="task-card" type="button" @click="triggerAction('模拟面试')">
          <span class="task-icon" aria-hidden="true"><el-icon><Microphone /></el-icon></span>
          <span class="task-copy">
            <strong>模拟面试训练</strong>
            <small>围绕目标岗位组织回答，获得可执行的反馈。</small>
          </span>
          <el-icon class="task-arrow" aria-hidden="true"><ArrowRight /></el-icon>
        </button>
      </section>
    </div>

    <section class="career-playbook" aria-labelledby="playbook-title">
      <header class="playbook-heading">
        <div>
          <p class="section-kicker">PREPARATION PLAYBOOK</p>
          <h2 id="playbook-title">把准备工作拆成可复盘的动作</h2>
        </div>
        <p>每一项建议都可以直接用在下一份简历、JD 或面试演练中。</p>
      </header>

      <ol class="guidance-list">
        <li>
          <span class="guidance-index tabular-nums">01</span>
          <div>
            <h3>用 STAR 结构呈现经历</h3>
            <p>说明情境、任务、行动与结果，让每一段经历都有清晰的贡献和证据。</p>
          </div>
        </li>
        <li>
          <span class="guidance-index tabular-nums">02</span>
          <div>
            <h3>投递前先拆解岗位要求</h3>
            <p>区分硬性条件、加分项与协作要求，再针对性调整简历与沟通重点。</p>
          </div>
        </li>
        <li>
          <span class="guidance-index tabular-nums">03</span>
          <div>
            <h3>把面试回答组织成故事</h3>
            <p>围绕问题、方案和结果练习表达，提前准备能够展开追问的项目案例。</p>
          </div>
        </li>
      </ol>
    </section>
  </section>
</template>

<script setup>
import {
  Aim,
  ArrowRight,
  DocumentChecked,
  Lightning,
  Microphone
} from '@element-plus/icons-vue'

defineProps({
  username: { type: String, default: '同学' }
})

const emit = defineEmits(['action'])

const triggerAction = (action) => emit('action', action)
</script>

<style scoped>
.dashboard {
  min-height: 100%;
  overflow-y: auto;
  padding: clamp(var(--space-6), 5vw, var(--space-12));
  background: var(--color-canvas);
}

.dashboard-header {
  max-width: var(--content-max-width);
  margin: 0 auto var(--space-10);
}

.dashboard-kicker,
.section-kicker,
.spotlight-kicker {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  margin: 0 0 var(--space-3);
  color: var(--color-primary);
  font-size: var(--font-size-caption);
  font-weight: 700;
  letter-spacing: 0.13em;
  line-height: var(--line-height-caption);
}

.dashboard-kicker::before {
  width: 1.5rem;
  height: 1px;
  background: currentColor;
  content: '';
}

.dashboard-title {
  margin-bottom: var(--space-3);
  color: var(--color-text-primary);
  font-size: clamp(1.9rem, 4vw, 2.5rem);
  font-weight: 700;
  letter-spacing: -0.035em;
  line-height: 1.2;
}

.dashboard-subtitle {
  max-width: 40rem;
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-body-large);
  line-height: var(--line-height-body-large);
}

.command-layout {
  display: grid;
  max-width: var(--content-max-width);
  grid-template-columns: minmax(0, 1.5fr) minmax(18rem, 0.9fr);
  gap: var(--space-6);
  margin: 0 auto var(--space-10);
}

.command-spotlight {
  position: relative;
  display: flex;
  min-height: 22rem;
  align-items: flex-end;
  overflow: hidden;
  padding: clamp(var(--space-6), 4vw, var(--space-10));
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-card, var(--radius-panel));
  background:
    radial-gradient(
      circle at 88% 15%,
      color-mix(in srgb, var(--color-cyan, var(--color-electric-blue, var(--color-primary))) 22%, transparent),
      transparent 25rem
    ),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--color-primary) 15%, var(--color-surface-elevated, var(--color-surface))),
      var(--color-surface-elevated, var(--color-surface)) 62%
    );
  box-shadow: var(--shadow-popover);
}

.command-spotlight::before {
  position: absolute;
  inset: 0;
  border: 1px solid color-mix(in srgb, var(--color-primary) 30%, transparent);
  border-radius: inherit;
  content: '';
  opacity: 0.75;
  pointer-events: none;
}

.spotlight-content {
  position: relative;
  z-index: 1;
  max-width: 31rem;
}

.spotlight-kicker {
  color: var(--color-cyan, var(--color-primary));
}

.spotlight-kicker .el-icon {
  font-size: 1rem;
}

.command-spotlight h2 {
  margin-bottom: var(--space-4);
  color: var(--color-text-primary);
  font-size: clamp(1.55rem, 3vw, 2.15rem);
  font-weight: 700;
  letter-spacing: -0.035em;
  line-height: 1.2;
}

.command-spotlight > .spotlight-content > p:not(.spotlight-kicker) {
  max-width: 38ch;
  margin-bottom: var(--space-8);
  color: var(--color-text-secondary);
  font-size: var(--font-size-body-large);
  line-height: 1.7;
}

.spotlight-footer {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-4);
  align-items: center;
}

.spotlight-action {
  --el-button-border-color: transparent;
  --el-button-bg-color: var(--color-primary);
  --el-button-hover-bg-color: var(--color-primary-hover);
  --el-button-active-bg-color: var(--color-primary-pressed);

  min-height: 2.75rem;
  background: linear-gradient(
    135deg,
    var(--color-primary),
    var(--color-electric-blue, var(--color-primary)) 60%,
    var(--color-cyan, var(--color-primary-hover))
  );
  box-shadow: 0 0.8rem 2.25rem color-mix(in srgb, var(--color-primary) 25%, transparent);
  font-weight: 650;
}

.spotlight-action .el-icon:last-child {
  margin-left: var(--space-1);
}

.spotlight-footer > span {
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.spotlight-orbit {
  position: absolute;
  top: 50%;
  right: clamp(-6rem, -3vw, -2rem);
  width: clamp(13rem, 25vw, 19rem);
  aspect-ratio: 1;
  transform: translateY(-50%);
}

.orbit-ring,
.orbit-core {
  position: absolute;
  display: grid;
  place-items: center;
  border-radius: 50%;
}

.orbit-ring {
  inset: 0;
  border: 1px solid color-mix(in srgb, var(--color-primary) 34%, transparent);
}

.orbit-ring--outer::after,
.orbit-ring--inner::after {
  position: absolute;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background: var(--color-cyan, var(--color-primary));
  box-shadow: 0 0 1.25rem var(--color-cyan, var(--color-primary));
  content: '';
}

.orbit-ring--outer::after {
  top: 14%;
  left: 15%;
}

.orbit-ring--inner {
  inset: 18%;
  border-color: color-mix(in srgb, var(--color-electric-blue, var(--color-primary)) 48%, transparent);
}

.orbit-ring--inner::after {
  right: 9%;
  bottom: 17%;
}

.orbit-core {
  inset: 37%;
  color: var(--color-on-primary);
  background: var(--color-primary);
  box-shadow: 0 0 3rem color-mix(in srgb, var(--color-primary) 48%, transparent);
  font-size: 1.35rem;
}

.quick-launch {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card, var(--radius-panel));
  background: var(--color-surface);
}

.quick-launch-heading {
  margin-bottom: var(--space-1);
}

.quick-launch-heading .section-kicker {
  margin-bottom: var(--space-1);
}

.quick-launch-heading > p:last-child {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-body);
  line-height: var(--line-height-body);
}

.task-card {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: 2.5rem minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
  color: var(--color-text-primary);
  cursor: pointer;
  text-align: left;
  transition:
    background-color var(--duration-control) var(--ease-standard),
    border-color var(--duration-control) var(--ease-standard),
    transform var(--duration-control) var(--ease-standard);
}

.task-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 3px;
}

.task-icon {
  display: grid;
  width: 2.5rem;
  height: 2.5rem;
  place-items: center;
  border-radius: var(--radius-control);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 1.15rem;
}

.task-copy {
  min-width: 0;
}

.task-copy strong,
.task-copy small {
  display: block;
}

.task-copy strong {
  margin-bottom: var(--space-1);
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
  font-weight: 650;
  line-height: var(--line-height-label);
}

.task-copy small {
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.task-arrow {
  color: var(--color-text-muted);
  font-size: 1rem;
  transition:
    color var(--duration-control) var(--ease-standard),
    transform var(--duration-control) var(--ease-standard);
}

.career-playbook {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding-top: var(--space-8);
  border-top: 1px solid var(--color-border);
}

.playbook-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(15rem, 0.65fr);
  gap: var(--space-8);
  align-items: end;
  margin-bottom: var(--space-6);
}

.playbook-heading .section-kicker {
  margin-bottom: var(--space-2);
}

.playbook-heading h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-section-title);
  font-weight: 650;
  line-height: var(--line-height-section-title);
}

.playbook-heading > p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-body);
  line-height: var(--line-height-body);
}

.guidance-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
  padding: 0;
  margin: 0;
  list-style: none;
}

.guidance-list li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-3);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.guidance-index {
  color: var(--color-primary);
  font-size: var(--font-size-caption);
  font-weight: 700;
  letter-spacing: 0.08em;
  line-height: var(--line-height-caption);
}

.guidance-list h3 {
  margin-bottom: var(--space-2);
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
  font-weight: 650;
  line-height: var(--line-height-label);
}

.guidance-list p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

@media (max-width: 980px) {
  .command-layout {
    grid-template-columns: 1fr;
  }

  .quick-launch {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quick-launch-heading {
    grid-column: 1 / -1;
  }

  .playbook-heading {
    grid-template-columns: 1fr;
    gap: var(--space-3);
  }
}

@media (max-width: 680px) {
  .dashboard {
    padding: var(--space-6) var(--space-4);
  }

  .dashboard-header {
    margin-bottom: var(--space-8);
  }

  .command-layout {
    gap: var(--space-4);
    margin-bottom: var(--space-8);
  }

  .command-spotlight {
    min-height: 0;
  }

  .spotlight-orbit {
    top: 3rem;
    right: -4rem;
    width: 11rem;
    transform: none;
  }

  .spotlight-content {
    max-width: calc(100% - 3rem);
  }

  .spotlight-footer {
    align-items: stretch;
  }

  .spotlight-action {
    width: 100%;
  }

  .quick-launch,
  .guidance-list {
    grid-template-columns: 1fr;
  }

  .quick-launch {
    padding: var(--space-4);
  }

  .career-playbook {
    padding-top: var(--space-6);
  }

  .guidance-list {
    gap: var(--space-4);
  }
}

@media (hover: hover) and (pointer: fine) {
  .task-card:hover {
    border-color: var(--color-border-strong);
    background: var(--color-surface-hover);
    transform: translateY(-2px);
  }

  .task-card:hover .task-arrow {
    color: var(--color-primary);
    transform: translateX(3px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .task-card:hover,
  .task-card:hover .task-arrow {
    transform: none;
  }
}
</style>
