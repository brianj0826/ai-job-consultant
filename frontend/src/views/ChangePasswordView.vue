<template>
  <main class="account-page account-page--security" data-testid="change-password-page">
    <div class="account-page__orbit account-page__orbit--near" aria-hidden="true"></div>
    <div class="account-page__orbit account-page__orbit--far" aria-hidden="true"></div>

    <section class="account-card account-card--security" aria-labelledby="change-password-title">
      <header class="account-card__header">
        <div class="account-card__brand" aria-hidden="true">
          <el-icon><Lock /></el-icon>
        </div>
        <p class="technical-label">ACCOUNT SECURITY</p>
        <h1 id="change-password-title">修改密码</h1>
        <p class="account-card__intro">
          {{ mustChangePassword
            ? '管理员已要求你设置新密码。完成修改前，其他功能将暂时不可用。'
            : '定期更新密码有助于保护你的会话与职业资料。' }}
        </p>
      </header>

      <el-alert
        v-if="mustChangePassword"
        class="account-card__alert"
        title="需要先修改密码"
        type="warning"
        :closable="false"
        show-icon
      />

      <el-form
        ref="formRef"
        class="account-form"
        :model="form"
        :rules="rules"
        label-position="top"
        data-testid="change-password-form"
        @submit.prevent="submit"
      >
        <el-form-item label="当前密码" prop="currentPassword">
          <el-input
            v-model="form.currentPassword"
            autocomplete="current-password"
            show-password
            type="password"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="form.newPassword"
            autocomplete="new-password"
            show-password
            type="password"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            autocomplete="new-password"
            show-password
            type="password"
          />
        </el-form-item>

        <p v-if="submitError" class="account-form__error" role="alert">{{ submitError }}</p>

        <el-button
          class="account-form__submit"
          native-type="submit"
          type="primary"
          :loading="submitting"
        >
          保存新密码
        </el-button>
      </el-form>

      <div class="account-card__actions">
        <el-button v-if="!mustChangePassword" text @click="goBack">暂不修改</el-button>
        <el-button text type="danger" @click="signOut">退出登录</el-button>
      </div>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { getErrorMessage } from '../api'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const auth = useAuth()
const { changePassword, currentUser, logout, mustChangePassword } = auth
const formRef = ref(null)
const submitting = ref(false)
const submitError = ref('')
const form = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const rules = {
  currentPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 128, message: '密码长度应为 8–128 个字符', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value && value === form.currentPassword) callback(new Error('新密码不能与当前密码相同'))
        else callback()
      },
      trigger: 'blur'
    }
  ],
  confirmPassword: [{
    validator: (_rule, value, callback) => {
      if (!value) callback(new Error('请再次输入新密码'))
      else if (value !== form.newPassword) callback(new Error('两次输入的新密码不一致'))
      else callback()
    },
    trigger: 'blur'
  }]
}

const destinationFor = (user) => (
  ['admin', 'super_admin'].includes(user?.role)
    ? { name: 'admin-overview' }
    : { name: 'workspace' }
)

const submit = async () => {
  if (submitting.value || !formRef.value) return
  submitError.value = ''
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const user = await changePassword(form.currentPassword, form.newPassword)
    ElMessage.success('密码已更新，请使用新密码继续。')
    await router.replace(destinationFor(user))
  } catch (error) {
    submitError.value = getErrorMessage(error, '密码修改失败，请稍后重试。')
  } finally {
    submitting.value = false
  }
}

const goBack = () => router.replace(destinationFor(currentUser.value))

const signOut = async () => {
  try {
    await logout()
    await router.replace({ name: 'login' })
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '退出登录失败，请检查网络后重试。'))
  }
}
</script>
