<template>
  <div class="welcome-container">
    <div class="welcome-card">
      <!-- 左侧品牌区 -->
      <div class="brand-side">
        <div class="brand-icon">💼</div>
        <h1 class="brand-title">职达</h1>
        <p class="brand-desc">AI 求职顾问 — 简历优化 × 岗位匹配 × 面试模拟</p>
        <div class="brand-features">
          <span>📄 简历智能分析</span>
          <span>🎯 岗位精准匹配</span>
          <span>💬 模拟面试点评</span>
          <span>📊 求职数据追踪</span>
        </div>
      </div>

      <!-- 右侧登录/注册区 -->
      <div class="form-side">
        <h2>{{ isRegister ? '创建账号' : '欢迎回来' }}</h2>
        <p class="form-sub">{{ isRegister ? '注册一个新账号开始使用' : '登录您的账号继续使用' }}</p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          @keyup.enter="handleSubmit"
          label-position="top"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              prefix-icon="User"
              size="large"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              prefix-icon="Lock"
              size="large"
              show-password
            />
          </el-form-item>

          <el-form-item v-if="isRegister" label="确认密码" prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              prefix-icon="Lock"
              size="large"
              show-password
            />
          </el-form-item>

          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleSubmit"
            class="submit-btn"
          >
            {{ isRegister ? '注 册' : '登 录' }}
          </el-button>
        </el-form>

        <p class="toggle-text">
          {{ isRegister ? '已有账号？' : '没有账号？' }}
          <el-link type="primary" @click="toggleMode">
            {{ isRegister ? '去登录' : '去注册' }}
          </el-link>
        </p>

        <p class="demo-hint">
          💡 也可直接登录体验（新用户名自动创建）
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { register, login } from '../api'
import { ElMessage } from 'element-plus'

const emit = defineEmits(['login-success'])

const isRegister = ref(false)
const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 3, message: '密码至少3个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    {
      validator: (rule, value, callback) => {
        if (value !== form.password) {
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
  isRegister.value = !isRegister.value
  form.password = ''
  form.confirmPassword = ''
}

const handleSubmit = async () => {
  if (!form.username || !form.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  if (isRegister.value && form.password !== form.confirmPassword) {
    ElMessage.warning('两次密码不一致')
    return
  }

  loading.value = true
  try {
    if (isRegister.value) {
      const res = await register(form.username, form.password)
      ElMessage.success(res.data.message || '注册成功')
      localStorage.setItem('ai_user_id', res.data.user_id)
      localStorage.setItem('ai_username', form.username)
      emit('login-success', res.data.user_id, form.username)
    } else {
      let res
      try {
        // 先尝试密码登录
        res = await login(form.username, form.password)
      } catch (e) {
        if (e.response?.status === 401) {
          ElMessage.error('用户名或密码错误')
          loading.value = false
          return
        }
        // 兼容旧版无密码登录
        res = await login(form.username)
      }
      localStorage.setItem('ai_user_id', res.data.user_id)
      localStorage.setItem('ai_username', form.username)
      emit('login-success', res.data.user_id, form.username)
    }
  } catch (e) {
    const msg = e.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ---- 页面容器：渐变背景 + 淡入动画 ---- */
.welcome-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background:
    radial-gradient(ellipse at 30% 20%, rgba(102, 126, 234, 0.4) 0%, transparent 60%),
    radial-gradient(ellipse at 70% 80%, rgba(118, 75, 162, 0.35) 0%, transparent 60%),
    linear-gradient(160deg, #667eea 0%, #5a6fd6 30%, #6b4ba2 70%, #764ba2 100%);
  background-size: 100% 100%, 100% 100%, 100% 100%;
  animation: bgPulse 8s ease-in-out infinite;
}
@keyframes bgPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.96; }
}

/* ---- 卡片：浮起质感 ---- */
.welcome-card {
  display: flex;
  width: 820px;
  min-height: 500px;
  background: rgba(255, 255, 255, 0.97);
  backdrop-filter: blur(20px);
  border-radius: 20px;
  box-shadow:
    0 4px 24px rgba(0, 0, 0, 0.06),
    0 16px 48px rgba(30, 30, 60, 0.12),
    0 32px 80px rgba(30, 30, 60, 0.08);
  overflow: hidden;
  animation: cardFadeIn 0.6s ease-out;
}
@keyframes cardFadeIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* ---- 左侧品牌区：多层渐变 + 光影 ---- */
.brand-side {
  flex: 1;
  position: relative;
  background:
    radial-gradient(circle at 20% 30%, rgba(255,255,255,0.15) 0%, transparent 50%),
    radial-gradient(circle at 80% 70%, rgba(102,126,234,0.4) 0%, transparent 50%),
    linear-gradient(160deg, #3b6fd4 0%, #2d5ec0 25%, #4a3f9e 65%, #3d2f8a 100%);
  color: #fff;
  padding: 52px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}
/* 左侧光影条纹 */
.brand-side::before {
  content: '';
  position: absolute;
  top: -60%;
  right: -30%;
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}
.brand-side::after {
  content: '';
  position: absolute;
  bottom: -20%;
  left: -10%;
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.brand-icon {
  font-size: 52px;
  margin-bottom: 16px;
  filter: drop-shadow(0 4px 8px rgba(0,0,0,0.15));
  animation: iconFloat 3s ease-in-out infinite;
  position: relative;
  z-index: 1;
}
@keyframes iconFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

.brand-title {
  font-size: 34px;
  font-weight: 800;
  margin: 0 0 10px;
  letter-spacing: 2px;
  position: relative;
  z-index: 1;
  text-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.brand-desc {
  font-size: 15px;
  opacity: 0.92;
  margin: 0 0 32px;
  line-height: 1.7;
  position: relative;
  z-index: 1;
  font-weight: 400;
  letter-spacing: 0.5px;
}

/* 功能列表 */
.brand-features {
  display: flex;
  flex-direction: column;
  gap: 14px;
  font-size: 14px;
  position: relative;
  z-index: 1;
}
.brand-features span {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(255,255,255,0.1);
  border-radius: 10px;
  backdrop-filter: blur(4px);
  transition: all 0.25s ease;
  border: 1px solid rgba(255,255,255,0.08);
}
.brand-features span:hover {
  background: rgba(255,255,255,0.18);
  transform: translateX(4px);
}

/* ---- 右侧表单：卡片质感 ---- */
.form-side {
  flex: 1;
  padding: 52px 44px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: #fff;
}
.form-side h2 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
  letter-spacing: 0.5px;
}
.form-sub {
  color: #999;
  font-size: 14px;
  margin: 0 0 28px;
}

/* ---- 输入框：柔和聚焦动效 ---- */
.form-side :deep(.el-input__wrapper) {
  border-radius: 10px;
  border: 1.5px solid #e8e8f0;
  box-shadow: none;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: #fafbfc;
}
.form-side :deep(.el-input__wrapper:hover) {
  border-color: #c0c8e0;
  background: #fff;
}
.form-side :deep(.el-input__wrapper.is-focus) {
  border-color: #5b7fff;
  box-shadow: 0 0 0 3px rgba(91, 127, 255, 0.12);
  background: #fff;
}
.form-side :deep(.el-form-item__label) {
  font-weight: 600;
  color: #444;
  font-size: 13px;
}

/* ---- 登录按钮：渐变 + 动效 ---- */
.submit-btn {
  width: 100%;
  margin-top: 12px;
  height: 46px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 2px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #5b7fff 0%, #6c5ce7 100%);
  box-shadow: 0 4px 16px rgba(91, 127, 255, 0.35);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.submit-btn:hover {
  background: linear-gradient(135deg, #4a6ef5 0%, #5b4bd5 100%);
  box-shadow: 0 6px 24px rgba(91, 127, 255, 0.45);
  transform: translateY(-1px);
}
.submit-btn:active {
  transform: translateY(0) scale(0.98);
  box-shadow: 0 2px 8px rgba(91, 127, 255, 0.3);
}

/* ---- 底部链接 ---- */
.toggle-text {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
  color: #999;
}
.demo-hint {
  text-align: center;
  margin-top: 10px;
  font-size: 12px;
  color: #c8c8d0;
}
</style>
