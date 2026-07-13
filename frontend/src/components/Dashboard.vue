<template>
  <section class="dashboard" aria-labelledby="dashboard-title">
    <div class="dashboard__inner">
      <header class="dashboard-header">
        <div>
          <p class="dashboard-kicker">CAREER COMMAND</p>
          <h1 id="dashboard-title" class="dashboard-title">欢迎回来，{{ username }}</h1>
          <p class="dashboard-subtitle">选择一个明确的下一步，让求职准备保持可推进。</p>
        </div>

        <el-button class="dashboard-chat" @click="triggerAction('chat')">
          <el-icon aria-hidden="true"><ChatDotRound /></el-icon>
          继续职业对话
          <el-icon class="dashboard-chat__arrow" aria-hidden="true"><ArrowRight /></el-icon>
        </el-button>
      </header>

      <div class="command-layout">
        <article class="resume-focus" aria-labelledby="resume-focus-title">
          <div class="resume-focus__aurora" aria-hidden="true"></div>
          <div class="resume-focus__orbit" aria-hidden="true">
            <span class="orbit orbit--outer"></span>
            <span class="orbit orbit--middle"></span>
            <span class="orbit orbit--inner"></span>
            <span class="orbit orbit--core"></span>
          </div>

          <div class="resume-focus__content">
            <div class="resume-focus__heading">
              <span class="resume-focus__icon" aria-hidden="true">
                <el-icon><DocumentChecked /></el-icon>
              </span>
              <div>
                <p class="section-kicker">PRIMARY FOCUS</p>
                <h2 id="resume-focus-title">简历分析</h2>
                <p>识别表达、结构和证据上的改进方向</p>
              </div>
            </div>

            <el-button
              class="resume-focus__action"
              type="primary"
              @click="triggerAction('career-resumes')"
            >
              开始分析
              <el-icon aria-hidden="true"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </article>

        <section class="quick-launch" aria-labelledby="quick-launch-title">
          <h2 id="quick-launch-title" class="sr-only">继续准备</h2>

          <button class="task-card" type="button" @click="triggerAction('career-jobs')">
            <span class="task-icon" aria-hidden="true"><el-icon><Aim /></el-icon></span>
            <span class="task-copy">
              <strong>岗位匹配</strong>
              <small>理解岗位要求，找准个人优势</small>
            </span>
            <el-icon class="task-arrow" aria-hidden="true"><ArrowRight /></el-icon>
          </button>

          <button class="task-card" type="button" @click="triggerAction('career-interviews')">
            <span class="task-icon task-icon--cyan" aria-hidden="true">
              <el-icon><Microphone /></el-icon>
            </span>
            <span class="task-copy">
              <strong>模拟面试</strong>
              <small>练习真实场景，提升表达自信</small>
            </span>
            <el-icon class="task-arrow" aria-hidden="true"><ArrowRight /></el-icon>
          </button>
        </section>
      </div>

      <section class="career-playbook" aria-labelledby="playbook-title">
        <header class="playbook-heading">
          <p class="section-kicker">PREPARATION PLAYBOOK</p>
          <h2 id="playbook-title">求职准备建议</h2>
        </header>

        <ol class="guidance-list">
          <li>
            <span class="guidance-index guidance-index--violet tabular-nums">1</span>
            <div>
              <h3>用 STAR 结构呈现经历</h3>
              <p>按情境、任务、行动、结果梳理关键经历，让成果更清晰可见。</p>
            </div>
          </li>
          <li>
            <span class="guidance-index guidance-index--blue tabular-nums">2</span>
            <div>
              <h3>投递前拆解岗位要求</h3>
              <p>提炼岗位的核心能力与关键词，对齐自身经历与证据。</p>
            </div>
          </li>
          <li>
            <span class="guidance-index guidance-index--cyan tabular-nums">3</span>
            <div>
              <h3>把面试回答组织成故事</h3>
              <p>围绕目标与挑战组织有逻辑的故事，更好应对面试官追问。</p>
            </div>
          </li>
        </ol>
      </section>
    </div>
  </section>
</template>

<script setup>
import {
  Aim,
  ArrowRight,
  ChatDotRound,
  DocumentChecked,
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
  background:
    radial-gradient(circle at 66% 4%, var(--color-aurora-blue-soft), transparent 30rem),
    radial-gradient(circle at 18% 76%, var(--color-aurora-violet-soft), transparent 32rem),
    var(--color-canvas);
}

.dashboard__inner {
  width: min(100%, calc(var(--content-max-width) + (var(--page-padding) * 2)));
  min-height: 100%;
  padding: clamp(var(--space-8), 4.5vw, var(--space-12)) var(--page-padding) var(--space-12);
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  gap: var(--space-6);
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: var(--space-8);
}

.dashboard-kicker,
.section-kicker {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  margin: 0 0 var(--space-2);
  color: var(--color-primary-text);
  font-size: var(--font-size-caption);
  font-weight: 700;
  letter-spacing: 0.14em;
  line-height: var(--line-height-caption);
}

.dashboard-kicker::before {
  width: 1.5rem;
  height: 1px;
  background: currentColor;
  content: '';
}

.dashboard-title {
  margin: 0 0 var(--space-2);
  color: var(--color-text-primary);
  font-size: clamp(2rem, 4vw, 2.625rem);
  font-weight: 720;
  letter-spacing: -0.04em;
  line-height: 1.18;
}

.dashboard-subtitle {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-body-large);
  line-height: var(--line-height-body-large);
}

.dashboard-chat {
  --el-button-bg-color: color-mix(in srgb, var(--color-surface) 74%, transparent);
  --el-button-border-color: var(--color-border);
  --el-button-hover-bg-color: var(--color-surface-hover);
  --el-button-hover-border-color: var(--color-border-strong);
  --el-button-text-color: var(--color-text-secondary);

  min-height: 2.75rem;
  flex: 0 0 auto;
  padding-inline: var(--space-4);
  backdrop-filter: blur(var(--glass-blur));
  font-weight: 600;
}

.dashboard-chat__arrow {
  margin-left: var(--space-1);
  transition: transform var(--duration-control) var(--ease-standard);
}

.command-layout {
  display: grid;
  grid-template-columns: minmax(0, 2.08fr) minmax(18rem, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-8);
}

.resume-focus,
.quick-launch {
  min-height: 24.5rem;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}

.resume-focus {
  position: relative;
  display: flex;
  align-items: center;
  overflow: hidden;
  padding: clamp(var(--space-8), 4vw, var(--space-12));
  isolation: isolate;
  background:
    linear-gradient(118deg, color-mix(in srgb, var(--color-surface) 96%, transparent) 0 54%, transparent 78%),
    var(--color-surface-subtle);
}

.resume-focus::before {
  position: absolute;
  z-index: -1;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(135deg, var(--color-aurora-violet-soft), transparent 42%);
  content: '';
  pointer-events: none;
}

.resume-focus__aurora {
  position: absolute;
  z-index: -1;
  right: -7%;
  bottom: -54%;
  width: 75%;
  height: 70%;
  border-radius: 50%;
  background: var(--aurora-gradient);
  filter: blur(3.5rem);
  opacity: 0.58;
  pointer-events: none;
}

.resume-focus__content {
  position: relative;
  z-index: 2;
  width: min(100%, 30rem);
}

.resume-focus__heading {
  display: flex;
  gap: var(--space-6);
  align-items: flex-start;
  margin-bottom: var(--space-12);
}

.resume-focus__icon {
  display: grid;
  width: 5.25rem;
  height: 5.25rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--color-primary) 44%, transparent);
  border-radius: 50%;
  background:
    radial-gradient(circle at 36% 28%, color-mix(in srgb, var(--color-on-primary) 32%, transparent), transparent 35%),
    var(--color-primary-soft);
  color: var(--color-primary-text);
  box-shadow:
    inset 0 0 1.5rem color-mix(in srgb, var(--color-primary) 18%, transparent),
    0 0 2.75rem color-mix(in srgb, var(--color-primary) 18%, transparent);
  font-size: 2rem;
}

.resume-focus .section-kicker {
  margin: 0 0 var(--space-1);
}

.resume-focus h2 {
  margin: 0 0 var(--space-2);
  color: var(--color-text-primary);
  font-size: clamp(2rem, 4vw, 2.75rem);
  font-weight: 740;
  letter-spacing: -0.04em;
  line-height: 1.16;
}

.resume-focus__heading p:last-child {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-body-large);
  line-height: var(--line-height-body-large);
}

.resume-focus__action {
  --el-button-bg-color: transparent;
  --el-button-border-color: transparent;
  --el-button-hover-border-color: transparent;
  --el-button-active-border-color: transparent;

  min-width: 15.625rem;
  min-height: 4.5rem;
  justify-content: center;
  padding-inline: var(--space-8);
  border: 0;
  background: var(--aurora-gradient);
  box-shadow: var(--aurora-glow);
  font-size: 1.0625rem;
  font-weight: 680;
}

.resume-focus__action .el-icon {
  margin-left: var(--space-4);
  font-size: 1.125rem;
  transition: transform var(--duration-control) var(--ease-standard);
}

.resume-focus__orbit {
  position: absolute;
  z-index: 1;
  top: 50%;
  right: -5.5rem;
  width: min(25rem, 46%);
  aspect-ratio: 1;
  transform: translateY(-50%);
  pointer-events: none;
}

.orbit {
  position: absolute;
  border: 1px solid color-mix(in srgb, var(--color-electric-blue) 48%, transparent);
  border-radius: 50%;
}

.orbit::after {
  position: absolute;
  width: 0.5rem;
  height: 0.5rem;
  border: 1px solid var(--color-electric-blue);
  border-radius: 50%;
  background: var(--color-surface-subtle);
  box-shadow: 0 0 1.25rem color-mix(in srgb, var(--color-electric-blue) 72%, transparent);
  content: '';
}

.orbit--outer {
  inset: 0;
  border-color: color-mix(in srgb, var(--color-primary) 58%, transparent);
}

.orbit--outer::after {
  top: 13%;
  left: 17%;
  border-color: var(--color-primary);
}

.orbit--middle {
  inset: 17%;
  border-style: dashed;
}

.orbit--middle::after {
  right: 10%;
  bottom: 20%;
}

.orbit--inner {
  inset: 33%;
}

.orbit--inner::after {
  bottom: -0.25rem;
  left: 12%;
}

.orbit--core {
  inset: 44%;
  border-color: color-mix(in srgb, var(--color-cyan) 65%, transparent);
  background: color-mix(in srgb, var(--color-electric-blue) 12%, transparent);
  box-shadow: 0 0 3rem color-mix(in srgb, var(--color-electric-blue) 30%, transparent);
}

.orbit--core::after {
  top: 50%;
  left: 50%;
  width: 0.75rem;
  height: 0.75rem;
  border: 0;
  background: var(--color-electric-blue);
  transform: translate(-50%, -50%);
}

.quick-launch {
  display: grid;
  min-width: 0;
  grid-template-rows: repeat(2, minmax(0, 1fr));
  overflow: hidden;
  background: color-mix(in srgb, var(--color-surface) 93%, transparent);
}

.task-card {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: 4.5rem minmax(0, 1fr) auto;
  gap: var(--space-6);
  align-items: center;
  padding: var(--space-8) var(--space-6);
  border: 0;
  background: transparent;
  color: var(--color-text-primary);
  cursor: pointer;
  text-align: left;
  transition:
    background-color var(--duration-control) var(--ease-standard),
    color var(--duration-control) var(--ease-standard);
}

.task-card + .task-card {
  border-top: 1px solid var(--color-border);
}

.task-card:focus-visible {
  position: relative;
  z-index: 1;
  outline: none;
  box-shadow:
    inset 0 0 0 2px var(--color-primary),
    inset 0 0 0 5px var(--color-focus-ring);
}

.task-icon {
  display: grid;
  width: 4.5rem;
  height: 4.5rem;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--color-primary) 36%, var(--color-border));
  border-radius: 50%;
  background: color-mix(in srgb, var(--color-primary-soft) 70%, transparent);
  color: var(--color-primary-text);
  font-size: 1.75rem;
}

.task-icon--cyan {
  border-color: color-mix(in srgb, var(--color-cyan) 40%, var(--color-border));
  background: color-mix(in srgb, var(--color-aurora-cyan-soft) 78%, transparent);
  color: var(--color-cyan);
}

.task-copy {
  min-width: 0;
}

.task-copy strong,
.task-copy small {
  display: block;
}

.task-copy strong {
  margin-bottom: var(--space-2);
  color: var(--color-text-primary);
  font-size: 1.25rem;
  font-weight: 680;
  letter-spacing: -0.015em;
  line-height: 1.45;
}

.task-copy small {
  color: var(--color-text-muted);
  font-size: var(--font-size-body);
  line-height: var(--line-height-body);
}

.task-arrow {
  color: var(--color-text-muted);
  font-size: 1.25rem;
  transition:
    color var(--duration-control) var(--ease-standard),
    transform var(--duration-control) var(--ease-standard);
}

.career-playbook {
  padding-top: var(--space-8);
  border-top: 1px solid var(--color-border);
}

.playbook-heading {
  margin-bottom: var(--space-6);
}

.playbook-heading .section-kicker {
  margin-bottom: var(--space-2);
}

.playbook-heading h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-section-title);
  font-weight: 680;
  letter-spacing: -0.02em;
  line-height: var(--line-height-section-title);
}

.guidance-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  padding: 0;
  margin: 0;
  list-style: none;
}

.guidance-list li {
  display: grid;
  min-width: 0;
  grid-template-columns: 2.75rem minmax(0, 1fr);
  gap: var(--space-5);
  padding: 0 var(--space-8);
}

.guidance-list li:first-child {
  padding-left: var(--space-3);
}

.guidance-list li + li {
  border-left: 1px solid var(--color-border);
}

.guidance-index {
  display: grid;
  width: 2.75rem;
  height: 2.75rem;
  place-items: center;
  border: 1px solid currentColor;
  border-radius: 50%;
  color: var(--color-primary-text);
  font-size: var(--font-size-body-large);
  font-weight: 700;
}

.guidance-index--blue {
  color: var(--color-electric-blue);
}

.guidance-index--cyan {
  color: var(--color-cyan);
}

.guidance-list h3 {
  margin: 0 0 var(--space-2);
  color: var(--color-text-primary);
  font-size: var(--font-size-body-large);
  font-weight: 680;
  line-height: var(--line-height-body-large);
}

.guidance-list p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-body);
  line-height: 1.75;
}

@media (max-width: 980px) {
  .command-layout {
    grid-template-columns: 1fr;
  }

  .resume-focus,
  .quick-launch {
    min-height: 22rem;
  }

  .quick-launch {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: 1fr;
  }

  .task-card + .task-card {
    border-top: 0;
    border-left: 1px solid var(--color-border);
  }

  .task-card {
    grid-template-columns: 3.5rem minmax(0, 1fr) auto;
    gap: var(--space-4);
  }

  .task-icon {
    width: 3.5rem;
    height: 3.5rem;
    font-size: 1.35rem;
  }

  .guidance-list li {
    padding-inline: var(--space-5);
  }
}

@media (max-width: 720px) {
  .dashboard__inner {
    padding-top: var(--space-8);
  }

  .dashboard-header {
    display: block;
    margin-bottom: var(--space-6);
  }

  .dashboard-title {
    font-size: 2rem;
  }

  .dashboard-chat {
    width: 100%;
    margin-top: var(--space-5);
  }

  .resume-focus {
    min-height: 25rem;
    align-items: flex-start;
    padding: var(--space-6);
  }

  .resume-focus__heading {
    display: block;
    margin-bottom: var(--space-8);
  }

  .resume-focus__icon {
    width: 4.25rem;
    height: 4.25rem;
    margin-bottom: var(--space-5);
    font-size: 1.625rem;
  }

  .resume-focus h2 {
    font-size: 2rem;
  }

  .resume-focus__action {
    width: 100%;
    min-width: 0;
    min-height: 3.5rem;
  }

  .resume-focus__orbit {
    top: auto;
    right: -4.5rem;
    bottom: -4.5rem;
    width: 17rem;
    transform: none;
    opacity: 0.72;
  }

  .quick-launch {
    min-height: 0;
    grid-template-columns: 1fr;
    grid-template-rows: repeat(2, minmax(9.5rem, auto));
  }

  .task-card {
    min-height: 9.5rem;
    padding: var(--space-5);
  }

  .task-card + .task-card {
    border-top: 1px solid var(--color-border);
    border-left: 0;
  }

  .guidance-list {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .guidance-list li,
  .guidance-list li:first-child {
    padding: var(--space-5) 0;
  }

  .guidance-list li + li {
    border-top: 1px solid var(--color-border);
    border-left: 0;
  }
}

@media (max-width: 420px) {
  .resume-focus {
    min-height: 27rem;
  }

  .task-card {
    grid-template-columns: 3rem minmax(0, 1fr) auto;
    gap: var(--space-3);
  }

  .task-icon {
    width: 3rem;
    height: 3rem;
    font-size: 1.2rem;
  }

  .task-copy strong {
    font-size: 1.0625rem;
  }
}

@media (hover: hover) and (pointer: fine) {
  .dashboard-chat:hover .dashboard-chat__arrow,
  .resume-focus__action:hover .el-icon,
  .task-card:hover .task-arrow {
    transform: translateX(0.25rem);
  }

  .task-card:hover {
    background: var(--color-surface-hover);
  }

  .task-card:hover .task-arrow {
    color: var(--color-primary-text);
  }
}

@media (prefers-reduced-motion: reduce) {
  .dashboard-chat__arrow,
  .resume-focus__action .el-icon,
  .task-arrow {
    transition: none;
  }

  .dashboard-chat:hover .dashboard-chat__arrow,
  .resume-focus__action:hover .el-icon,
  .task-card:hover .task-arrow {
    transform: none;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .dashboard-chat,
  .quick-launch {
    background: var(--color-surface);
    backdrop-filter: none;
  }

  .resume-focus__aurora {
    opacity: 0.22;
    filter: blur(2rem);
  }
}
</style>
