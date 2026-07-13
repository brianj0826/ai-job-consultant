<template>
  <main class="account-page account-page--denied" data-testid="forbidden-page">
    <div class="account-page__orbit account-page__orbit--near" aria-hidden="true"></div>
    <div class="account-page__orbit account-page__orbit--far" aria-hidden="true"></div>

    <section class="account-card account-card--compact account-card--denied" aria-labelledby="forbidden-title">
      <header class="account-card__header">
        <div class="account-card__brand account-card__brand--danger" aria-hidden="true">
          <el-icon><Lock /></el-icon>
        </div>
        <p class="technical-label">ACCESS DENIED</p>
        <h1 id="forbidden-title">无权访问此页面</h1>
        <p class="account-card__intro">当前账号不具备管理员权限。你仍可返回职业工作台继续使用个人功能。</p>
      </header>
      <div class="account-card__actions account-card__actions--centered">
        <el-button type="primary" @click="router.replace({ name: 'workspace' })">返回职业工作台</el-button>
        <el-button @click="signOut">退出登录</el-button>
      </div>
    </section>
  </main>
</template>

<script setup>
import { Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { getErrorMessage } from '../api'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { logout } = useAuth()

const signOut = async () => {
  try {
    await logout()
    await router.replace({ name: 'login' })
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '退出登录失败，请检查网络后重试。'))
  }
}
</script>
