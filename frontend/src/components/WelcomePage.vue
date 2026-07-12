<template>
  <main class="welcome-container precision-aurora" aria-labelledby="welcome-heading">
    <div class="aurora-orb aurora-orb--violet" aria-hidden="true"></div>
    <div class="aurora-orb aurora-orb--cyan" aria-hidden="true"></div>

    <section class="welcome-card precision-aurora__panel" aria-label="职达账户入口">
      <section class="brand-side" aria-labelledby="welcome-heading">
        <div class="brand-content">
          <div class="brand-mark" aria-hidden="true">
            <el-icon><Connection /></el-icon>
          </div>
          <p class="brand-kicker">CAREER INTELLIGENCE</p>
          <h1 id="welcome-heading" class="brand-title">
            职达
            <span>Career Intelligence Console</span>
          </h1>
          <p class="brand-desc">
            用清晰的洞察和可执行的下一步，推进每一次求职决策。
          </p>

          <ul class="brand-features" aria-label="平台能力">
            <li>
              <el-icon aria-hidden="true"><DocumentChecked /></el-icon>
              <span><strong>简历洞察</strong><small>识别表达与结构的改进方向</small></span>
            </li>
            <li>
              <el-icon aria-hidden="true"><Aim /></el-icon>
              <span><strong>岗位匹配</strong><small>将目标 JD 与现有经历逐项对照</small></span>
            </li>
            <li>
              <el-icon aria-hidden="true"><ChatDotRound /></el-icon>
              <span><strong>面试训练</strong><small>围绕目标岗位组织高质量演练</small></span>
            </li>
          </ul>
        </div>
      </section>

      <section class="form-side" aria-labelledby="auth-heading">
        <div class="form-panel">
          <p class="form-kicker">{{ isRegister ? 'CREATE YOUR WORKSPACE' : 'SECURE SIGN IN' }}</p>
          <h2 id="auth-heading" class="form-title">
            {{ isRegister ? '创建你的工作台' : '欢迎回来' }}
          </h2>
          <p class="form-sub">
            {{ isRegister ? '注册账号，开始管理你的职业准备。' : '登录后继续你的求职准备。' }}
          </p>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            class="auth-form"
            label-position="top"
            @keyup.enter="handleSubmit"
          >
            <el-form-item label="用户名" prop="username">
              <el-input
                v-model="form.username"
                :prefix-icon="User"
                autocomplete="username"
                placeholder="请输入用户名"
                size="large"
              />
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <el-input
                v-model="form.password"
                :prefix-icon="Lock"
                :autocomplete="isRegister ? 'new-password' : 'current-password'"
                placeholder="请输入密码"
                show-password
                size="large"
                type="password"
              />
            </el-form-item>

            <div
              class="confirm-field"
              :class="{ 'confirm-field--open': isRegister }"
              :aria-hidden="isRegister ? undefined : 'true'"
              :inert="!isRegister"
            >
              <div class="confirm-field__inner">
                <el-form-item label="确认密码" prop="confirmPassword">
                  <el-input
                    v-model="form.confirmPassword"
                    :prefix-icon="Lock"
                    :disabled="!isRegister"
                    autocomplete="new-password"
                    placeholder="请再次输入密码"
                    show-password
                    size="large"
                    type="password"
                  />
                </el-form-item>
              </div>
            </div>

            <Transition name="submit-error">
              <p v-if="submitError" class="submit-error" role="alert">{{ submitError }}</p>
            </Transition>

            <el-button
              class="submit-btn"
              :disabled="retryAfterSeconds > 0"
              :loading="loading"
              size="large"
              type="primary"
              @click="handleSubmit"
            >
              {{ retryAfterSeconds > 0
                ? `${retryAfterSeconds} 秒后重试`
                : (isRegister ? '创建账号' : '登录并继续') }}
            </el-button>
          </el-form>

          <p class="mode-toggle">
            {{ isRegister ? '已有账号？' : '首次使用？' }}
            <el-link class="mode-link" type="primary" @click="toggleMode">
              {{ isRegister ? '去登录' : '创建账号' }}
            </el-link>
          </p>

          <p class="form-note">
            <el-icon aria-hidden="true"><InfoFilled /></el-icon>
            登录凭据通过安全 Cookie 会话处理，浏览器不会保存你的密码。
          </p>
        </div>
      </section>
    </section>
  </main>
</template>

<script setup>
import { nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import {
  Aim,
  ChatDotRound,
  Connection,
  DocumentChecked,
  InfoFilled,
  Lock,
  User
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getErrorMessage } from '../api'
import { useAuth } from '../composables/useAuth'

const emit = defineEmits(['login-success'])

const isRegister = ref(false)
const loading = ref(false)
const retryAfterSeconds = ref(0)
const formRef = ref(null)
const submitError = ref('')
const { login, register } = useAuth()
const form = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})
let retryAfterTimer = null

const startRetryAfter = (seconds) => {
  if (retryAfterTimer !== null) clearInterval(retryAfterTimer)
  retryAfterSeconds.value = Math.max(1, Number.parseInt(seconds || 1, 10))
  retryAfterTimer = setInterval(() => {
    retryAfterSeconds.value = Math.max(0, retryAfterSeconds.value - 1)
    if (retryAfterSeconds.value === 0) {
      clearInterval(retryAfterTimer)
      retryAfterTimer = null
    }
  }, 1000)
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 64, message: '用户名长度应为 2–64 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value?.length > 128) callback(new Error('密码不能超过 128 个字符'))
        else if (isRegister.value && value?.length < 8) callback(new Error('注册密码至少需要 8 个字符'))
        else callback()
      },
      trigger: 'blur'
    }
  ],
  confirmPassword: [
    {
      validator: (rule, value, callback) => {
        if (!isRegister.value) {
          callback()
        } else if (!value) {
          callback(new Error('请再次输入密码'))
        } else if (value !== form.password) {
          callback(new Error('两次密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const toggleMode = () => {
  if (loading.value) return
  isRegister.value = !isRegister.value
  submitError.value = ''
  form.password = ''
  form.confirmPassword = ''
  nextTick(() => formRef.value?.clearValidate())
}

const focusFirstInvalidField = async () => {
  await nextTick()
  const firstInvalidInput = formRef.value?.$el?.querySelector('.el-form-item.is-error input')
  firstInvalidInput?.focus()
}

const handleSubmit = async () => {
  if (loading.value || retryAfterSeconds.value > 0 || !formRef.value) return
  submitError.value = ''
  const isValid = await formRef.value.validate().catch(() => false)
  if (!isValid) {
    await focusFirstInvalidField()
    return
  }

  loading.value = true
  try {
    if (isRegister.value) {
      const user = await register(form.username, form.password)
      ElMessage.success('注册成功')
      emit('login-success', user)
    } else {
      try {
        const user = await login(form.username, form.password)
        emit('login-success', user)
      } catch (e) {
        if (e.response?.status === 401) {
          submitError.value = '用户名或密码错误'
          await nextTick()
          formRef.value?.$el?.querySelector('input[type="password"]')?.focus()
          return
        }
        throw e
      }
    }
  } catch (e) {
    if (e?.status === 429) startRetryAfter(e.retryAfter)
    submitError.value = getErrorMessage(e, '操作失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

onBeforeUnmount(() => {
  if (retryAfterTimer !== null) clearInterval(retryAfterTimer)
})
</script>

<style scoped>
.welcome-container.precision-aurora {
  position: relative;
  display: grid;
  min-height: 100dvh;
  isolation: isolate;
  overflow: clip;
  overflow-anchor: none;
  padding: 0;
  background:
    radial-gradient(
      circle at 7% 102%,
      color-mix(in srgb, var(--color-primary) 34%, transparent),
      transparent 30rem
    ),
    radial-gradient(
      circle at 45% 105%,
      color-mix(in srgb, var(--color-electric-blue) 28%, transparent),
      transparent 28rem
    ),
    linear-gradient(135deg, var(--color-canvas-deep), var(--color-canvas));
}

.aurora-orb {
  position: absolute;
  z-index: -1;
  border-radius: 50%;
  filter: blur(8px);
  opacity: 0.64;
  pointer-events: none;
}

.aurora-orb--violet {
  bottom: -24rem;
  left: -17rem;
  width: 46rem;
  height: 46rem;
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--color-primary) 50%, transparent),
    transparent 68%
  );
}

.aurora-orb--cyan {
  right: 42%;
  bottom: -24rem;
  width: 43rem;
  height: 43rem;
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--color-cyan) 34%, transparent),
    transparent 68%
  );
}

.welcome-card.precision-aurora__panel {
  display: grid;
  width: 100%;
  min-height: 100dvh;
  grid-template-columns: minmax(0, 44fr) minmax(0, 56fr);
  overflow: hidden;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  animation: panel-arrive var(--duration-hero, 420ms) var(--ease-enter, var(--ease-standard)) both;
}

.brand-side {
  position: relative;
  display: flex;
  min-width: 0;
  overflow: hidden;
  padding: clamp(var(--space-12), 6vw, var(--space-24));
  color: var(--color-text-primary);
  background:
    radial-gradient(
      circle at 18% 108%,
      color-mix(in srgb, var(--color-primary) 42%, transparent),
      transparent 29rem
    ),
    radial-gradient(
      circle at 88% 102%,
      color-mix(in srgb, var(--color-electric-blue) 34%, transparent),
      transparent 27rem
    ),
    linear-gradient(155deg, var(--color-canvas-deep), var(--color-canvas));
}

.brand-side::before {
  position: absolute;
  right: -19rem;
  bottom: -19rem;
  width: 49rem;
  height: 49rem;
  border-radius: 50%;
  background:
    radial-gradient(
      circle,
      color-mix(in srgb, var(--color-electric-blue) 92%, transparent) 0 0.38rem,
      color-mix(in srgb, var(--color-electric-blue) 18%, transparent) 0.42rem 1.1rem,
      transparent 1.15rem
    ),
    repeating-radial-gradient(
      circle,
      transparent 0 4.75rem,
      color-mix(in srgb, var(--color-electric-blue) 45%, transparent) 4.8rem 4.86rem,
      transparent 4.92rem 7.85rem
    );
  content: '';
  opacity: 0.9;
  pointer-events: none;
}

.brand-side::after {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(color-mix(in srgb, var(--color-border) 42%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--color-border) 42%, transparent) 1px, transparent 1px);
  background-size: 3rem 3rem;
  content: '';
  mask-image: linear-gradient(145deg, transparent 24%, var(--color-canvas) 82%, transparent);
  opacity: 0.24;
  pointer-events: none;
}

.brand-content {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  max-width: 34rem;
  flex-direction: column;
  justify-content: flex-start;
  padding-block: clamp(var(--space-4), 3vh, var(--space-8));
}

.brand-mark {
  display: none;
}

.brand-kicker,
.form-kicker,
.section-kicker {
  margin-bottom: var(--space-3);
  font-size: var(--font-size-caption);
  font-weight: 700;
  letter-spacing: 0.13em;
  line-height: var(--line-height-caption);
}

.brand-kicker {
  color: var(--color-primary);
  font-family: var(--font-mono);
}

.brand-title {
  margin-bottom: var(--space-6);
  color: var(--color-text-primary);
  font-size: clamp(3.5rem, 5.5vw, 4.75rem);
  font-weight: 750;
  letter-spacing: -0.06em;
  line-height: 1;
}

.brand-title span {
  display: block;
  margin-top: var(--space-4);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-label);
  font-weight: 600;
  letter-spacing: 0.08em;
  line-height: var(--line-height-body);
  text-transform: uppercase;
}

.brand-desc {
  max-width: 25ch;
  margin-bottom: clamp(var(--space-12), 7vh, var(--space-20));
  color: var(--color-text-secondary);
  font-size: var(--font-size-body-large);
  line-height: 1.85;
}

.brand-features {
  display: grid;
  gap: var(--space-8);
  max-width: 32rem;
  padding: 0;
  margin: 0;
  list-style: none;
}

.brand-features li {
  display: grid;
  grid-template-columns: 3.5rem minmax(0, 1fr);
  gap: var(--space-5);
  align-items: center;
}

.brand-features li:nth-child(1) {
  --feature-accent: var(--color-primary);
}

.brand-features li:nth-child(2) {
  --feature-accent: var(--color-electric-blue);
}

.brand-features li:nth-child(3) {
  --feature-accent: var(--color-cyan);
}

.brand-features > li > .el-icon {
  display: grid;
  width: 3.5rem;
  height: 3.5rem;
  place-items: center;
  margin: 0;
  border: 1px solid color-mix(in srgb, var(--feature-accent) 52%, transparent);
  border-radius: 50%;
  background: color-mix(in srgb, var(--feature-accent) 10%, transparent);
  box-shadow: inset 0 0 1.5rem color-mix(in srgb, var(--feature-accent) 8%, transparent);
  color: var(--feature-accent);
  font-size: 1.35rem;
}

.brand-features strong,
.brand-features small {
  display: block;
}

.brand-features strong {
  margin-bottom: var(--space-1);
  color: var(--color-text-primary);
  font-size: var(--font-size-component-title);
  font-weight: 650;
  line-height: var(--line-height-component-title);
}

.brand-features small {
  color: var(--color-text-muted);
  font-size: var(--font-size-body);
  line-height: var(--line-height-body);
}

.form-side {
  position: relative;
  display: grid;
  min-width: 0;
  place-items: center;
  padding: var(--space-12) clamp(var(--space-8), 5vw, var(--space-20));
  border-left: 1px solid var(--color-border);
  background:
    radial-gradient(
      circle at 58% 8%,
      color-mix(in srgb, var(--color-electric-blue) 9%, transparent),
      transparent 24rem
    ),
    linear-gradient(145deg, var(--color-canvas), var(--color-canvas-deep));
}

.form-panel {
  display: flex;
  width: min(100%, 45rem);
  min-height: min(48rem, calc(100dvh - var(--space-24)));
  box-sizing: border-box;
  flex-direction: column;
  justify-content: center;
  padding: clamp(var(--space-8), 3.5vw, var(--space-12));
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-card);
  background: color-mix(in srgb, var(--color-surface) 76%, transparent);
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--color-text-primary) 5%, transparent);
  backdrop-filter: blur(12px);
}

.form-kicker {
  color: var(--color-primary);
  font-family: var(--font-mono);
}

.form-title {
  margin-bottom: var(--space-3);
  color: var(--color-text-primary);
  font-size: clamp(2rem, 3.2vw, 2.5rem);
  font-weight: 720;
  letter-spacing: -0.045em;
  line-height: 1.15;
}

.form-sub {
  margin-bottom: var(--space-10);
  color: var(--color-text-secondary);
  font-size: var(--font-size-body-large);
  line-height: var(--line-height-body-large);
}

.auth-form :deep(.el-form-item) {
  margin-bottom: var(--space-5);
}

.auth-form {
  min-height: 21.5rem;
}

.confirm-field {
  display: grid;
  grid-template-rows: 0fr;
  opacity: 0;
  transition:
    grid-template-rows var(--duration-content, 220ms) var(--ease-enter, var(--ease-standard)),
    opacity var(--duration-content-exit, 160ms) var(--ease-exit, var(--ease-standard));
}

.confirm-field--open {
  grid-template-rows: 1fr;
  opacity: 1;
  transition-timing-function: var(--ease-enter, var(--ease-standard));
}

.confirm-field__inner {
  min-height: 0;
  overflow: hidden;
}

.submit-error {
  margin: calc(var(--space-2) * -1) 0 var(--space-3);
  color: var(--color-danger);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.submit-error-enter-active {
  transition:
    max-height var(--duration-content-exit, 160ms) var(--ease-enter, var(--ease-standard)),
    opacity var(--duration-content-exit, 160ms) var(--ease-enter, var(--ease-standard)),
    transform var(--duration-content-exit, 160ms) var(--ease-enter, var(--ease-standard));
}

.submit-error-leave-active {
  transition:
    max-height var(--duration-content-exit, 160ms) var(--ease-exit, var(--ease-standard)),
    opacity var(--duration-content-exit, 160ms) var(--ease-exit, var(--ease-standard)),
    transform var(--duration-content-exit, 160ms) var(--ease-exit, var(--ease-standard));
}

.submit-error-enter-from,
.submit-error-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-4px);
}

.submit-error-enter-to,
.submit-error-leave-from {
  max-height: 3rem;
}

.auth-form :deep(.el-form-item__label) {
  padding-bottom: var(--space-2);
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
  font-weight: 650;
}

.auth-form :deep(.el-input__wrapper) {
  min-height: 3.5rem;
  padding-inline: var(--space-4);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--color-surface-subtle) 82%, transparent);
  box-shadow: none;
}

.auth-form :deep(.el-input__wrapper:hover),
.auth-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-primary);
  background: var(--color-surface-subtle);
  box-shadow: var(--focus-ring);
}

.auth-form :deep(.el-input__prefix),
.auth-form :deep(.el-input__suffix) {
  color: var(--color-text-secondary);
  font-size: 1.15rem;
}

.auth-form :deep(.el-form-item__error) {
  position: static;
  padding-top: var(--space-1);
  animation: form-error-arrive var(--duration-content-exit, 160ms) var(--ease-enter, var(--ease-standard)) both;
}

.submit-btn {
  width: 100%;
  min-height: 3.5rem;
  margin-top: var(--space-2);
  border-color: transparent;
  background: var(--aurora-gradient);
  box-shadow: var(--aurora-glow);
  font-size: var(--font-size-component-title);
  font-weight: 680;
  transition:
    box-shadow var(--duration-control) var(--ease-standard),
    transform var(--duration-control) var(--ease-standard),
    filter var(--duration-control) var(--ease-standard);
}

.submit-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 3px;
}

.mode-toggle {
  display: flex;
  min-height: 3.5rem;
  box-sizing: border-box;
  align-items: center;
  justify-content: center;
  margin: var(--space-4) 0 0;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--color-surface-subtle) 52%, transparent);
  color: var(--color-text-secondary);
  font-size: var(--font-size-component-title);
  text-align: center;
}

.mode-link {
  margin-left: var(--space-1);
  font-size: inherit;
  font-weight: 650;
}

.form-note {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  margin: var(--space-6) 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.form-note .el-icon {
  flex: 0 0 auto;
  margin-top: 0.08rem;
  color: var(--color-primary);
}

@keyframes panel-arrive {
  from {
    opacity: 0;
    transform: translateY(var(--space-4));
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes form-error-arrive {
  from {
    opacity: 0;
    transform: translateY(-3px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (hover: hover) and (pointer: fine) {
  .submit-btn:hover:not(.is-disabled) {
    box-shadow: 0 1.2rem 2.8rem color-mix(in srgb, var(--color-primary) 34%, transparent);
    filter: brightness(1.06);
    transform: translateY(-1px);
  }
}

@supports not (backdrop-filter: blur(1px)) {
  .form-panel {
    background: var(--color-surface);
  }
}

@media (max-width: 1024px) {
  .brand-side {
    padding: var(--space-10) var(--space-8);
  }

  .brand-content {
    max-width: 28rem;
  }

  .brand-title {
    font-size: clamp(3rem, 6vw, 4rem);
  }

  .brand-desc {
    margin-bottom: var(--space-12);
  }

  .brand-features {
    gap: var(--space-6);
  }

  .brand-features li {
    grid-template-columns: 3rem minmax(0, 1fr);
    gap: var(--space-4);
  }

  .brand-features > li > .el-icon {
    width: 3rem;
    height: 3rem;
  }

  .brand-features small {
    font-size: var(--font-size-caption);
  }

  .form-side {
    padding: var(--space-8);
  }

  .form-panel {
    min-height: min(48rem, calc(100dvh - var(--space-16)));
    padding: var(--space-10);
  }
}

@media (max-width: 767px) {
  .welcome-container.precision-aurora {
    display: block;
    overflow-x: clip;
    overflow-y: visible;
  }

  .welcome-card.precision-aurora__panel {
    min-height: 100dvh;
    grid-template-columns: minmax(0, 1fr);
    overflow: visible;
  }

  .aurora-orb {
    display: none;
  }

  .brand-side {
    min-height: 14rem;
    padding: var(--space-8) var(--space-6);
    background:
      radial-gradient(
        circle at 86% 112%,
        color-mix(in srgb, var(--color-electric-blue) 34%, transparent),
        transparent 18rem
      ),
      linear-gradient(155deg, var(--color-canvas-deep), var(--color-canvas));
  }

  .brand-side::before {
    right: -11rem;
    bottom: -16rem;
    width: 28rem;
    height: 28rem;
  }

  .brand-content {
    max-width: none;
    padding: 0;
  }

  .brand-kicker {
    margin-bottom: var(--space-2);
  }

  .brand-title {
    margin-bottom: var(--space-3);
    font-size: clamp(2.5rem, 14vw, 3.25rem);
  }

  .brand-title span {
    margin-top: var(--space-2);
  }

  .brand-desc {
    max-width: 28ch;
    margin: 0;
    font-size: var(--font-size-body);
    line-height: var(--line-height-body-large);
  }

  .brand-features {
    display: none;
  }

  .form-side {
    min-height: calc(100dvh - 14rem);
    place-items: start center;
    padding: var(--space-4);
    border-top: 1px solid var(--color-border);
    border-left: 0;
  }

  .form-panel {
    width: 100%;
    min-height: 0;
    padding: var(--space-8) var(--space-5) var(--space-6);
    backdrop-filter: blur(8px);
  }

  .form-title {
    font-size: var(--font-size-page-title);
    line-height: var(--line-height-page-title);
  }

  .form-sub {
    margin-bottom: var(--space-6);
  }

  .auth-form {
    min-height: 0;
  }

  .auth-form :deep(.el-input__wrapper),
  .submit-btn,
  .mode-toggle {
    min-height: 3.25rem;
  }
}

@media (max-width: 420px) {
  .brand-side {
    min-height: 12.5rem;
    padding: var(--space-6) var(--space-5);
  }

  .brand-kicker,
  .brand-title span {
    display: none;
  }

  .brand-title {
    margin-bottom: var(--space-3);
    font-size: 2.5rem;
  }

  .form-side {
    min-height: calc(100dvh - 12.5rem);
    padding: var(--space-3);
  }

  .form-panel {
    padding: var(--space-6) var(--space-4) var(--space-5);
  }

  .form-note {
    margin-top: var(--space-5);
  }
}

@media (prefers-reduced-motion: reduce) {
  .welcome-card.precision-aurora__panel {
    animation: none;
  }

  .confirm-field,
  .submit-error-enter-active,
  .submit-error-leave-active {
    transition-duration: 0.01ms;
  }

  .auth-form :deep(.el-form-item__error) {
    animation: none;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .form-panel {
    background: var(--color-surface);
    backdrop-filter: none;
  }

  .aurora-orb {
    display: none;
  }
}
</style>
