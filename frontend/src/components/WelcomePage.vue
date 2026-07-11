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
  --aurora-gradient: linear-gradient(
    135deg,
    var(--color-primary) 0%,
    var(--color-electric-blue, var(--color-primary)) 52%,
    var(--color-cyan, var(--color-primary-hover)) 100%
  );

  position: relative;
  display: grid;
  min-height: 100dvh;
  place-items: center;
  isolation: isolate;
  overflow: clip;
  overflow-anchor: none;
  padding: var(--space-6);
  background:
    radial-gradient(
      circle at 12% 18%,
      color-mix(in srgb, var(--color-primary) 42%, transparent),
      transparent 34rem
    ),
    radial-gradient(
      circle at 88% 80%,
      color-mix(in srgb, var(--color-cyan, var(--color-electric-blue, var(--color-primary))) 28%, transparent),
      transparent 30rem
    ),
    linear-gradient(
      145deg,
      var(--color-canvas-deep, var(--color-canvas)),
      var(--color-canvas)
    );
}

.aurora-orb {
  position: absolute;
  z-index: -1;
  border-radius: 50%;
  filter: blur(1px);
  opacity: 0.8;
  pointer-events: none;
}

.aurora-orb--violet {
  top: -16rem;
  left: -13rem;
  width: 35rem;
  height: 35rem;
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--color-primary) 42%, transparent),
    transparent 68%
  );
}

.aurora-orb--cyan {
  right: -17rem;
  bottom: -18rem;
  width: 39rem;
  height: 39rem;
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--color-cyan, var(--color-electric-blue, var(--color-primary))) 30%, transparent),
    transparent 68%
  );
}

.welcome-card.precision-aurora__panel {
  display: grid;
  width: min(100%, 73rem);
  min-height: 38rem;
  grid-template-columns: minmax(0, 0.95fr) minmax(22rem, 1.05fr);
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-dialog);
  background: var(--color-surface-glass, var(--color-surface));
  box-shadow: var(--shadow-dialog);
  backdrop-filter: blur(18px);
  animation: panel-arrive var(--duration-hero, 420ms) var(--ease-enter, var(--ease-standard)) both;
}

.brand-side {
  position: relative;
  display: flex;
  min-width: 0;
  overflow: hidden;
  padding: clamp(var(--space-8), 5vw, var(--space-16));
  color: var(--color-on-primary);
  background:
    linear-gradient(
      115deg,
      color-mix(in srgb, var(--color-primary) 88%, var(--color-canvas-deep, var(--color-canvas))),
      color-mix(in srgb, var(--color-electric-blue, var(--color-primary)) 78%, var(--color-canvas-deep, var(--color-canvas)))
    );
}

.brand-side::before {
  position: absolute;
  top: -12rem;
  right: -14rem;
  width: 31rem;
  height: 31rem;
  border: 1px solid color-mix(in srgb, var(--color-on-primary) 28%, transparent);
  border-radius: 50%;
  box-shadow:
    0 0 0 3.5rem color-mix(in srgb, var(--color-on-primary) 5%, transparent),
    0 0 0 7rem color-mix(in srgb, var(--color-on-primary) 4%, transparent);
  content: '';
  opacity: 0.85;
}

.brand-side::after {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(
    color-mix(in srgb, var(--color-on-primary) 6%, transparent) 1px,
    transparent 1px
  );
  background-size: 2.75rem 2.75rem;
  content: '';
  mask-image: linear-gradient(to bottom, transparent, var(--color-canvas) 20%, transparent);
  opacity: 0.6;
  pointer-events: none;
}

.brand-content {
  position: relative;
  z-index: 1;
  display: flex;
  max-width: 28rem;
  flex-direction: column;
  justify-content: center;
}

.brand-mark {
  display: grid;
  width: 3rem;
  height: 3rem;
  place-items: center;
  margin-bottom: var(--space-8);
  border: 1px solid color-mix(in srgb, var(--color-on-primary) 42%, transparent);
  border-radius: var(--radius-card, var(--radius-panel));
  background: color-mix(in srgb, var(--color-on-primary) 13%, transparent);
  box-shadow: 0 0 2.5rem color-mix(in srgb, var(--color-cyan, var(--color-on-primary)) 36%, transparent);
  font-size: 1.35rem;
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
  color: color-mix(in srgb, var(--color-on-primary) 76%, transparent);
}

.brand-title {
  margin-bottom: var(--space-5);
  color: var(--color-on-primary);
  font-size: clamp(2.45rem, 5vw, 3.5rem);
  font-weight: 700;
  letter-spacing: -0.045em;
  line-height: 1.04;
}

.brand-title span {
  display: block;
  margin-top: var(--space-3);
  color: color-mix(in srgb, var(--color-on-primary) 78%, transparent);
  font-size: var(--font-size-body);
  font-weight: 500;
  letter-spacing: 0.03em;
  line-height: var(--line-height-body);
}

.brand-desc {
  max-width: 29ch;
  margin-bottom: var(--space-10);
  color: color-mix(in srgb, var(--color-on-primary) 86%, transparent);
  font-size: var(--font-size-body-large);
  line-height: 1.7;
}

.brand-features {
  display: grid;
  gap: var(--space-4);
  padding: 0;
  margin: 0;
  list-style: none;
}

.brand-features li {
  display: grid;
  grid-template-columns: 1.25rem minmax(0, 1fr);
  gap: var(--space-3);
  align-items: start;
  padding-top: var(--space-3);
  border-top: 1px solid color-mix(in srgb, var(--color-on-primary) 18%, transparent);
}

.brand-features .el-icon {
  margin-top: var(--space-1);
  color: var(--color-cyan, var(--color-on-primary));
  font-size: 1.15rem;
}

.brand-features strong,
.brand-features small {
  display: block;
}

.brand-features strong {
  margin-bottom: var(--space-1);
  color: var(--color-on-primary);
  font-size: var(--font-size-label);
  font-weight: 600;
  line-height: var(--line-height-label);
}

.brand-features small {
  color: color-mix(in srgb, var(--color-on-primary) 73%, transparent);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.form-side {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  padding: clamp(var(--space-8), 5vw, var(--space-16));
  background: var(--color-surface);
}

.form-kicker {
  color: var(--color-primary);
}

.form-title {
  margin-bottom: var(--space-2);
  color: var(--color-text-primary);
  font-size: clamp(1.65rem, 3vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.2;
}

.form-sub {
  margin-bottom: var(--space-8);
  color: var(--color-text-secondary);
  font-size: var(--font-size-body);
  line-height: var(--line-height-body);
}

.auth-form :deep(.el-form-item) {
  margin-bottom: var(--space-5);
}

.auth-form {
  min-height: 22rem;
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
  color: var(--color-text-secondary);
  font-weight: 600;
}

.auth-form :deep(.el-input__wrapper) {
  min-height: 2.75rem;
  background: var(--color-surface-subtle);
}

.auth-form :deep(.el-input__wrapper:hover),
.auth-form :deep(.el-input__wrapper.is-focus) {
  background: var(--color-surface);
}

.auth-form :deep(.el-form-item__error) {
  position: static;
  padding-top: var(--space-1);
  animation: form-error-arrive var(--duration-content-exit, 160ms) var(--ease-enter, var(--ease-standard)) both;
}

.submit-btn {
  width: 100%;
  min-height: 2.75rem;
  margin-top: var(--space-2);
  border-color: transparent;
  background: var(--aurora-gradient);
  box-shadow: 0 1rem 2.5rem color-mix(in srgb, var(--color-primary) 26%, transparent);
  font-weight: 650;
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
  margin: var(--space-6) 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-body);
  text-align: center;
}

.mode-link {
  margin-left: var(--space-1);
  font-weight: 600;
}

.form-note {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  margin: var(--space-4) 0 0;
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
  .welcome-card.precision-aurora__panel {
    background: var(--color-surface);
  }
}

@media (max-width: 820px) {
  .welcome-container.precision-aurora {
    padding: var(--space-4);
  }

  .welcome-card.precision-aurora__panel {
    width: min(100%, 36rem);
    min-height: 0;
    grid-template-columns: 1fr;
    backdrop-filter: blur(10px);
  }

  .brand-side {
    min-height: 16rem;
    padding: var(--space-8);
  }

  .brand-content {
    max-width: none;
  }

  .brand-mark {
    width: 2.5rem;
    height: 2.5rem;
    margin-bottom: var(--space-4);
  }

  .brand-title {
    font-size: clamp(2rem, 8vw, 2.65rem);
  }

  .brand-desc {
    margin-bottom: var(--space-6);
  }

  .brand-features {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-3);
  }

  .brand-features li {
    grid-template-columns: 1.15rem minmax(0, 1fr);
  }

  .brand-features small {
    display: none;
  }

  .form-side {
    padding: var(--space-8);
  }
}

@media (max-width: 480px) {
  .welcome-container.precision-aurora {
    display: block;
    padding: var(--space-3);
  }

  .welcome-card.precision-aurora__panel {
    margin: var(--space-3) 0;
  }

  .brand-side,
  .form-side {
    padding: var(--space-6);
  }

  .brand-side {
    min-height: 0;
  }

  .brand-desc {
    max-width: 100%;
  }

  .brand-features {
    grid-template-columns: 1fr;
  }

  .brand-features li {
    padding-top: var(--space-2);
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
  .welcome-card.precision-aurora__panel {
    background: var(--color-surface);
    backdrop-filter: none;
  }

  .aurora-orb {
    display: none;
  }
}
</style>
