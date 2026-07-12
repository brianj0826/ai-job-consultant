<template>
  <div class="sidebar-panel">
    <header class="sidebar-brand">
      <div class="sidebar-brand__mark" aria-hidden="true">
        <el-icon :size="20"><Briefcase /></el-icon>
      </div>
      <div class="sidebar-brand__copy">
        <span class="sidebar-brand__name">职达</span>
        <span class="sidebar-brand__meta">Career Intelligence</span>
      </div>
      <button
        v-if="showCloseButton"
        class="sidebar-close"
        type="button"
        aria-label="关闭导航"
        title="关闭导航"
        @click="$emit('close-navigation')"
      >
        <el-icon :size="20" aria-hidden="true"><Close /></el-icon>
      </button>
    </header>

    <nav class="sidebar-navigation" aria-label="工作台功能">
      <button class="sidebar-home" type="button" @click="$emit('go-home')">
        <el-icon :size="18" aria-hidden="true"><House /></el-icon>
        <span>职业工作台</span>
      </button>

      <el-collapse v-model="activePanels" class="sidebar-collapse">
        <el-collapse-item name="chat">
          <template #title>
            <span class="collapse-title">
              <el-icon :size="17" aria-hidden="true"><ChatDotRound /></el-icon>
              <span>会话</span>
            </span>
          </template>

          <div class="session-picker">
            <el-select
              v-model="currentSessionId"
              class="session-picker__select"
              :disabled="sessionActionPending"
              placeholder="选择会话"
              size="small"
              @change="switchSession"
            >
              <el-option v-for="session in sessions" :key="session.id" :label="session.name" :value="session.id" />
            </el-select>
            <el-button
              class="icon-button"
              size="small"
              :disabled="!currentSessionId || sessionActionPending"
              :loading="renamingSession"
              aria-label="重命名当前会话"
              title="重命名当前会话"
              @click="handleRenameSession"
            >
              <el-icon :size="15" aria-hidden="true"><EditPen /></el-icon>
            </el-button>
          </div>

          <div class="button-stack">
            <el-button
              type="primary"
              size="small"
              :loading="creatingSession"
              :disabled="sessionActionPending && !creatingSession"
              @click="newSession"
            >
              <el-icon :size="15" aria-hidden="true"><Plus /></el-icon>
              <span>新建对话</span>
            </el-button>
            <el-button
              type="danger"
              plain
              size="small"
              :loading="clearingSession"
              :disabled="!currentSessionId || (sessionActionPending && !clearingSession)"
              @click="clearSession"
            >
              <el-icon :size="15" aria-hidden="true"><Delete /></el-icon>
              <span>清空会话</span>
            </el-button>
            <div class="button-grid">
              <el-button
                size="small"
                :loading="exportingSession"
                :disabled="sessionActionPending && !exportingSession"
                @click="exportSession"
              >
                <el-icon :size="15" aria-hidden="true"><Download /></el-icon>
                <span>导出</span>
              </el-button>
              <el-button size="small" @click="$emit('show-analytics')">
                <el-icon :size="15" aria-hidden="true"><DataAnalysis /></el-icon>
                <span>数据</span>
              </el-button>
            </div>
          </div>
        </el-collapse-item>

        <el-collapse-item name="kb">
          <template #title>
            <span class="collapse-title">
              <el-icon :size="17" aria-hidden="true"><FolderOpened /></el-icon>
              <span>知识库</span>
            </span>
          </template>

          <el-tag
            v-if="knowledgeStatus === 'loading' && !hasKnowledgeSnapshot"
            type="info"
            effect="plain"
            size="small"
            class="knowledge-status"
          >
            <el-icon class="knowledge-status__spinner" :size="13" aria-hidden="true"><Loading /></el-icon>
            <span>正在加载知识库</span>
          </el-tag>
          <el-tag
            v-else-if="knowledgeStatus === 'error' && !hasKnowledgeSnapshot"
            type="danger"
            effect="plain"
            size="small"
            class="knowledge-status"
          >
            <el-icon :size="13" aria-hidden="true"><WarningFilled /></el-icon>
            <span>知识库加载失败</span>
          </el-tag>
          <el-tag v-else-if="docCount > 0" type="success" effect="plain" size="small" class="knowledge-status">
            <el-icon :size="13" aria-hidden="true"><CircleCheck /></el-icon>
            <span>{{ docCount }} 个文档块</span>
          </el-tag>
          <el-tag v-else-if="hasKnowledgeSnapshot" type="warning" effect="plain" size="small" class="knowledge-status">
            <el-icon :size="13" aria-hidden="true"><WarningFilled /></el-icon>
            <span>知识库为空</span>
          </el-tag>

          <p
            v-if="knowledgeStatus === 'loading' && hasKnowledgeSnapshot"
            class="knowledge-refreshing"
            role="status"
          >
            正在刷新知识库…
          </p>

          <p
            v-if="knowledgeStatus === 'error' && hasKnowledgeSnapshot"
            class="knowledge-warning"
            role="status"
          >
            <el-icon :size="14" aria-hidden="true"><WarningFilled /></el-icon>
            <span>{{ knowledgeError }}，当前仍显示上次加载的数据。</span>
          </p>

          <div v-if="docSources.length" class="source-list">
            <div v-for="(source, index) in docSources" :key="index" class="source-item">
              <el-icon :size="15" class="source-item__icon" aria-hidden="true">
                <Link v-if="source.type === 'web'" />
                <Document v-else />
              </el-icon>
              <span :title="source.source" class="source-name">{{ source.source }}</span>
              <div class="source-item__actions">
                <el-tag :type="source.type === 'web' ? 'warning' : 'info'" effect="plain" size="small">
                  {{ source.type === 'web' ? '网页' : '文档' }}
                </el-tag>
                <el-button
                  class="source-delete"
                  type="danger"
                  size="small"
                  circle
                  :loading="deletingSource === source.source"
                  :disabled="uploadingDocument || (Boolean(deletingSource) && deletingSource !== source.source)"
                  :aria-label="`删除来源 ${source.source}`"
                  @click="handleDeleteSource(source.source)"
                >
                  <el-icon :size="14" aria-hidden="true"><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>

          <el-upload
            class="upload-control"
            :http-request="uploadFile"
            :show-file-list="false"
            :disabled="knowledgeMutationPending"
            accept=".pdf,.txt,.md,.docx"
          >
            <el-button type="primary" plain size="small" :loading="uploadingDocument" :disabled="knowledgeMutationPending">
              <el-icon :size="15" aria-hidden="true"><DocumentAdd /></el-icon>
              <span>上传文档</span>
            </el-button>
          </el-upload>
        </el-collapse-item>

        <el-collapse-item name="career">
          <template #title>
            <span class="collapse-title">
              <el-icon :size="17" aria-hidden="true"><Aim /></el-icon>
              <span>求职工具</span>
            </span>
          </template>

          <div class="career-resource-list" aria-label="结构化职业资源">
            <RouterLink
              v-for="item in careerNavigation"
              :key="item.routeName"
              class="sidebar-career-link"
              :to="{ name: item.routeName }"
              @click="$emit('close-navigation')"
            >
              <el-icon :size="17" aria-hidden="true">
                <component :is="careerIcons[item.resource]" />
              </el-icon>
              <span>{{ item.label }}</span>
            </RouterLink>
          </div>

          <template v-if="docSources.length">
            <div v-if="resumeSource" class="resume-file">
              <el-icon :size="15" aria-hidden="true"><Document /></el-icon>
              <span :title="resumeSource.title || resumeSource.source">{{ resumeSource.title || resumeSource.source }}</span>
            </div>

            <div class="jd-input-area">
              <div class="jd-input-area__heading">
                <span class="jd-input-area__label">
                  <el-icon :size="15" aria-hidden="true"><Files /></el-icon>
                  <span>目标岗位 JD</span>
                </span>
                <el-button size="small" :loading="fetchingJD" @click="handleFetchJD">
                  <el-icon :size="14" aria-hidden="true"><Link /></el-icon>
                  <span>链接导入</span>
                </el-button>
              </div>
              <el-input v-model="jdText" type="textarea" :rows="5" placeholder="粘贴岗位 JD" size="small" />
              <div class="button-grid jd-actions">
                <el-button type="success" size="small" :disabled="!jdText || !resumeSource" @click="handleMatchJob">
                  <el-icon :size="15" aria-hidden="true"><Aim /></el-icon>
                  <span>匹配岗位</span>
                </el-button>
                <el-button type="warning" size="small" :disabled="!jdText" @click="handleGenQuestions">
                  <el-icon :size="15" aria-hidden="true"><ChatDotRound /></el-icon>
                  <span>生成题目</span>
                </el-button>
              </div>
            </div>
          </template>
        </el-collapse-item>

        <el-collapse-item name="settings">
          <template #title>
            <span class="collapse-title">
              <el-icon :size="17" aria-hidden="true"><Moon /></el-icon>
              <span>设置</span>
            </span>
          </template>

          <label class="setting-row">
            <span class="setting-row__label">深色模式</span>
            <el-switch v-model="isDark" size="small" aria-label="切换深色模式" @change="toggleDark" />
          </label>
          <div class="settings-actions">
            <el-button size="small" plain @click="$emit('change-password')">
              <el-icon :size="14" aria-hidden="true"><EditPen /></el-icon>
              <span>修改密码</span>
            </el-button>
            <el-button v-if="isAdmin" size="small" type="warning" plain @click="$emit('open-admin')">
              <el-icon :size="14" aria-hidden="true"><DataAnalysis /></el-icon>
              <span>管理控制台</span>
            </el-button>
          </div>
          <p class="status-bar" aria-live="polite">
            <span :class="['status-dot', backendOnline ? 'status-on' : 'status-off']" aria-hidden="true"></span>
            <el-icon :size="14" aria-hidden="true"><Connection /></el-icon>
            <span>{{ backendOnline ? '服务正常' : '服务离线' }}</span>
          </p>
        </el-collapse-item>
      </el-collapse>
    </nav>

    <footer class="sidebar-account">
      <div class="sidebar-account__avatar" aria-hidden="true">
        <el-icon :size="16"><User /></el-icon>
      </div>
      <div class="sidebar-account__identity">
        <span class="sidebar-account__name">{{ currentUsername || '未登录' }}</span>
        <span class="sidebar-account__meta">求职工作台</span>
      </div>
      <el-button class="sidebar-account__logout" text type="danger" size="small" @click="$emit('logout')">
        <el-icon :size="15" aria-hidden="true"><SwitchButton /></el-icon>
        <span>退出</span>
      </el-button>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Aim,
  Briefcase,
  ChatDotRound,
  ChatLineRound,
  CircleCheck,
  Close,
  Connection,
  DataAnalysis,
  Delete,
  Document,
  DocumentAdd,
  Download,
  EditPen,
  Files,
  FolderOpened,
  House,
  Link,
  Loading,
  Moon,
  Plus,
  SwitchButton,
  User,
  WarningFilled
} from '@element-plus/icons-vue'
import {
  createSession,
  deleteSession,
  deleteSource,
  fetchUrlContent,
  getDocStatus,
  getHealth,
  getMessages,
  getSessions,
  renameSession,
  uploadPDF
} from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { careerNavigation } from '../career/resources'

const careerIcons = {
  resumes: Document,
  jobs: Briefcase,
  applications: Aim,
  interviews: ChatLineRound,
  reports: DataAnalysis,
  skills: CircleCheck
}

const props = defineProps({
  currentUsername: { type: String, default: '' },
  userId: { type: Number, default: null },
  isAdmin: { type: Boolean, default: false },
  previewMode: { type: Boolean, default: false },
  showCloseButton: { type: Boolean, default: false }
})

const emit = defineEmits(['session-changed', 'new-session', 'clear-session', 'pdf-uploaded', 'show-analytics', 'logout', 'change-password', 'open-admin', 'quick-chat', 'go-home', 'close-navigation'])

const resumeSource = computed(() => docSources.value.find(source => source.type === 'file') || null)

const activePanels = ref(['chat'])
const sessions = ref([])
const currentSessionId = ref(null)
const docCount = ref(0)
const docSources = ref([])
const knowledgeStatus = ref('idle')
const knowledgeError = ref('')
const hasKnowledgeSnapshot = ref(false)
const deletingSource = ref(null)
const uploadingDocument = ref(false)
const creatingSession = ref(false)
const clearingSession = ref(false)
const renamingSession = ref(false)
const exportingSession = ref(false)
const initializingUserData = ref(false)
const jdText = ref('')
const fetchingJD = ref(false)
const sessionActionPending = computed(() => (
  creatingSession.value ||
  clearingSession.value ||
  renamingSession.value ||
  exportingSession.value ||
  initializingUserData.value
))
const knowledgeMutationPending = computed(() => (
  uploadingDocument.value || Boolean(deletingSource.value) || initializingUserData.value
))

const handleMatchJob = () => {
  if (!jdText.value) return
  const message = `请根据以下岗位JD，帮我匹配我的简历：\n\n${jdText.value}`
  emit('quick-chat', message)
}

const handleFetchJD = async () => {
  if (fetchingJD.value) return
  fetchingJD.value = true
  try {
    const { value: url } = await ElMessageBox.prompt('请输入招聘页面的 URL', '链接导入 JD', {
      confirmButtonText: '抓取',
      cancelButtonText: '取消',
      inputPlaceholder: 'https://www.zhipin.com/...'
    })
    if (!url || !url.trim()) return
    const res = await fetchUrlContent(url.trim())
    const title = res.data.title || ''
    const text = res.data.text || ''
    jdText.value = `${title ? `【${title}】\n` : ''}${text}`
    ElMessage.success('JD 内容已导入')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('抓取失败，请检查 URL 是否正确')
  } finally {
    fetchingJD.value = false
  }
}

const handleGenQuestions = () => {
  if (!jdText.value) return
  const message = `请根据以下岗位JD生成5道面试题：\n\n${jdText.value}`
  emit('quick-chat', message)
}

const initUserData = async () => {
  if (!props.userId || initializingUserData.value) return
  initializingUserData.value = true
  try {
    currentSessionId.value = null
    sessions.value = []
    docSources.value = []
    docCount.value = 0
    hasKnowledgeSnapshot.value = false

    await Promise.all([loadSessions(), loadDocStatus()])

    if (sessions.value.length === 0) {
      const now = new Date()
      const name = `${now.toLocaleDateString()} ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
      const newRes = await createSession(name)
      currentSessionId.value = newRes.data.session_id
      emit('new-session', currentSessionId.value)
      await loadSessions()
    } else {
      currentSessionId.value = sessions.value[0].id
      await switchSession(currentSessionId.value)
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '用户数据加载失败，请稍后重试')
  } finally {
    initializingUserData.value = false
  }
}

watch(() => props.userId, (newVal) => {
  if (newVal && !props.previewMode) initUserData()
})

const loadSessions = async () => {
  if (!props.userId) return
  const res = await getSessions()
  sessions.value = res.data
  if (currentSessionId.value && !sessions.value.some(session => session.id === currentSessionId.value)) {
    currentSessionId.value = null
  }
}

const switchSession = (sessionId) => {
  emit('session-changed', sessionId)
}

const newSession = async () => {
  if (!props.userId || sessionActionPending.value) return
  creatingSession.value = true
  try {
    const now = new Date()
    const name = `${now.toLocaleDateString()} ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    const res = await createSession(name)
    currentSessionId.value = res.data.session_id
    emit('new-session', currentSessionId.value)
    await loadSessions()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '新建会话失败')
  } finally {
    creatingSession.value = false
  }
}

const clearSession = async () => {
  if (!currentSessionId.value || sessionActionPending.value) return
  clearingSession.value = true
  try {
    await ElMessageBox.confirm(
      '确定要清空当前会话吗？所有对话记录将被永久删除。',
      '确认清空',
      { confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteSession(currentSessionId.value)
    currentSessionId.value = null
    emit('clear-session')
    await loadSessions()
    if (sessions.value.length) {
      currentSessionId.value = sessions.value[0].id
      switchSession(currentSessionId.value)
    } else {
      currentSessionId.value = null
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('清空会话失败')
  } finally {
    clearingSession.value = false
  }
}

const exportSession = async () => {
  if (exportingSession.value || sessionActionPending.value) return
  if (!currentSessionId.value) {
    ElMessage.warning('请先选择会话')
    return
  }
  exportingSession.value = true
  try {
    const res = await getMessages(currentSessionId.value)
    const messages = res.data
    if (!messages.length) {
      ElMessage.info('当前没有对话记录')
      return
    }
    const text = messages.map(message => `${message.role === 'user' ? '用户' : '助手'}：${message.content}`).join('\n\n')
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `对话记录_${new Date().toLocaleString()}.txt`
    anchor.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败')
  } finally {
    exportingSession.value = false
  }
}

const uploadFile = async (option) => {
  if (knowledgeMutationPending.value) return
  const file = option.file
  const alreadyExists = docSources.value.some(source => source.source === file.name)
  if (alreadyExists) {
    ElMessage.info('该文件已在当前知识库中，无需重复上传')
    return
  }

  uploadingDocument.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await uploadPDF(formData)

    if (res.status === 200) {
      ElMessage.success(res.data.message || '文档上传成功，知识库已更新')
      emit('pdf-uploaded')
      await loadDocStatus()
      if (currentSessionId.value) await switchSession(currentSessionId.value)
    } else {
      ElMessage.error('上传返回异常状态')
    }
  } catch {
    ElMessage.error('上传失败，请稍后重试')
  } finally {
    uploadingDocument.value = false
  }
}

let knowledgeRequestId = 0
const loadDocStatus = async () => {
  if (props.userId === null || props.userId === undefined) return
  const requestId = ++knowledgeRequestId
  knowledgeStatus.value = 'loading'
  knowledgeError.value = ''
  try {
    const res = await getDocStatus()
    if (requestId !== knowledgeRequestId) return
    docCount.value = res.data.doc_count
    docSources.value = res.data.sources || []
    hasKnowledgeSnapshot.value = true
    knowledgeStatus.value = 'ready'
  } catch (e) {
    if (requestId !== knowledgeRequestId) return
    knowledgeError.value = e.response?.data?.detail || '知识库刷新失败'
    knowledgeStatus.value = 'error'
  }
}

defineExpose({ loadDocStatus })

const isDark = ref(false)
const toggleDark = () => {
  document.documentElement.classList.toggle('dark', isDark.value)
  document.documentElement.dataset.theme = isDark.value ? 'dark' : 'light'
  localStorage.setItem('ai_dark_mode', isDark.value ? '1' : '0')
}

const handleRenameSession = async () => {
  if (!currentSessionId.value || sessionActionPending.value) return
  renamingSession.value = true
  try {
    const { value } = await ElMessageBox.prompt('请输入新名称', '重命名会话', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: sessions.value.find(session => session.id === currentSessionId.value)?.name || ''
    })
    if (value && value.trim()) {
      await renameSession(currentSessionId.value, value.trim())
      ElMessage.success('已重命名')
      await loadSessions()
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('重命名失败')
  } finally {
    renamingSession.value = false
  }
}

const backendOnline = ref(true)
let statusTimer = null
const checkBackendStatus = async () => {
  try {
    await getHealth()
    backendOnline.value = true
  } catch {
    backendOnline.value = false
  }
}

const handleDeleteSource = async (source) => {
  if (!props.userId || knowledgeMutationPending.value) return
  deletingSource.value = source
  try {
    await ElMessageBox.confirm(
      `确定要删除来源「${source}」的所有内容吗？此操作不可恢复。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteSource(source)
    ElMessage.success('已删除')
    await loadDocStatus()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  } finally {
    deletingSource.value = null
  }
}

onMounted(() => {
  if (props.userId && !props.previewMode) initUserData()
  isDark.value = document.documentElement.classList.contains('dark')
  if (props.previewMode) {
    backendOnline.value = false
    hasKnowledgeSnapshot.value = true
    knowledgeStatus.value = 'ready'
  } else {
    checkBackendStatus()
    statusTimer = setInterval(checkBackendStatus, 30000)
  }
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
})
</script>

<style scoped>
.sidebar-panel {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100%;
  color: var(--color-text-primary);
}

.sidebar-brand {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 64px;
  padding: var(--space-1) var(--space-2) var(--space-6);
  background: var(--color-surface);
}

.sidebar-brand__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 36px;
  width: 36px;
  height: 36px;
  border: 1px solid color-mix(in srgb, var(--color-primary) 34%, var(--color-border));
  border-radius: var(--radius-control);
  background: var(--aurora-gradient-soft);
  color: var(--color-primary);
  box-shadow: inset 0 0 18px var(--color-aurora-blue-soft);
}

.sidebar-brand__copy,
.sidebar-account__identity {
  display: grid;
  min-width: 0;
}

.sidebar-brand__copy {
  flex: 1;
}

.sidebar-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 44px;
  width: 44px;
  height: 44px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition:
    color var(--duration-control) var(--ease-standard),
    border-color var(--duration-control) var(--ease-standard),
    background-color var(--duration-control) var(--ease-standard);
}

.sidebar-close:hover {
  border-color: var(--color-border-strong);
  background: var(--color-surface-hover);
  color: var(--color-text-primary);
}

.sidebar-close:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.sidebar-brand__name {
  color: var(--color-text-primary);
  font-size: var(--font-size-section-title);
  font-weight: 700;
  line-height: var(--line-height-section-title);
}

.sidebar-brand__meta,
.sidebar-account__meta {
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-family: var(--font-mono);
  line-height: var(--line-height-caption);
  letter-spacing: 0.025em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-navigation {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding-right: var(--space-1);
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.sidebar-home {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  min-height: 52px;
  padding: 0 var(--space-4);
  margin-bottom: var(--space-3);
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--color-primary) 18%, transparent);
  border-radius: var(--radius-control);
  background: linear-gradient(90deg, var(--color-primary-soft), var(--color-aurora-blue-soft));
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition:
    border-color var(--duration-control) var(--ease-standard),
    background-color var(--duration-control) var(--ease-standard),
    color var(--duration-control) var(--ease-standard);
}

.sidebar-home::before {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 3px;
  background: var(--aurora-gradient);
  content: '';
}

.sidebar-home .el-icon {
  color: var(--color-primary);
}

.sidebar-home:hover {
  border-color: color-mix(in srgb, var(--color-primary) 34%, var(--color-border));
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--color-primary-soft) 86%, var(--color-surface)),
    var(--color-aurora-blue-soft)
  );
  color: var(--color-text-primary);
}

.sidebar-home:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.career-resource-list {
  display: grid;
  gap: var(--space-1);
  margin-bottom: var(--space-4);
}

.sidebar-career-link {
  display: flex;
  min-height: 42px;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  font-weight: 550;
  text-decoration: none;
  transition:
    border-color var(--duration-control) var(--ease-standard),
    background-color var(--duration-control) var(--ease-standard),
    color var(--duration-control) var(--ease-standard);
}

.sidebar-career-link:hover {
  border-color: var(--color-border-strong);
  background: var(--color-surface-hover);
  color: var(--color-text-primary);
}

.sidebar-career-link.router-link-active {
  border-color: color-mix(in srgb, var(--color-primary) 24%, transparent);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  box-shadow: inset 2px 0 var(--color-primary), inset 18px 0 28px var(--color-aurora-violet-soft);
}

.sidebar-career-link:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.sidebar-navigation:has(.sidebar-career-link.router-link-active) .sidebar-home {
  border-color: transparent;
  background: transparent;
  color: var(--color-text-secondary);
}

.sidebar-navigation:has(.sidebar-career-link.router-link-active) .sidebar-home::before {
  opacity: 0;
}

.sidebar-navigation:has(.sidebar-career-link.router-link-active) .sidebar-home .el-icon {
  color: currentColor;
}

.sidebar-collapse {
  display: flex;
  flex: 1;
  flex-direction: column;
  border: 0;
}

.sidebar-collapse :deep(.el-collapse-item) {
  flex: 0 0 auto;
  margin-bottom: var(--space-2);
}

.sidebar-collapse :deep(.el-collapse-item:last-child) {
  margin-top: auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.sidebar-collapse :deep(.el-collapse-item__header) {
  min-height: 48px;
  padding: 0 var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  font-weight: 600;
  line-height: var(--line-height-label);
  transition:
    background-color var(--duration-control) var(--ease-standard),
    color var(--duration-control) var(--ease-standard);
}

.sidebar-collapse :deep(.el-collapse-item__header:hover) {
  border-color: var(--color-border);
  background: var(--color-surface-hover);
  color: var(--color-text-primary);
}

.sidebar-collapse :deep(.el-collapse-item__header.is-active) {
  border-color: color-mix(in srgb, var(--color-primary) 18%, transparent);
  background: color-mix(in srgb, var(--color-primary-soft) 62%, transparent);
  color: var(--color-primary);
}

.sidebar-collapse :deep(.el-collapse-item__header:focus-visible) {
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.sidebar-collapse :deep(.el-collapse-item__arrow) {
  margin-right: var(--space-1);
  color: var(--color-text-muted);
}

.sidebar-collapse :deep(.el-collapse-item__wrap) {
  border: 0;
  background: transparent;
}

.sidebar-collapse :deep(.el-collapse-item__content) {
  padding: var(--space-3) var(--space-1) var(--space-5) var(--space-3);
  border-left: 1px solid var(--color-border);
}

.collapse-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
}

.session-picker,
.button-grid,
.tool-btns,
.jd-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-2);
}

.session-picker__select {
  min-width: 0;
}

.icon-button {
  width: 36px;
  min-height: 36px;
  padding: 0;
}

.button-stack {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.button-stack :deep(.el-button),
.button-grid :deep(.el-button),
.upload-control :deep(.el-button) {
  justify-content: center;
  width: 100%;
  min-height: 36px;
  margin: 0;
}

.button-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.knowledge-status {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  max-width: 100%;
  min-height: 28px;
}

.knowledge-refreshing,
.knowledge-warning {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1);
  margin: var(--space-2) 0 0;
  padding: var(--space-2);
  border-radius: var(--radius-control);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.knowledge-refreshing {
  background: var(--color-surface-subtle);
  color: var(--color-text-muted);
}

.knowledge-warning {
  border: 1px solid color-mix(in srgb, var(--color-warning) 32%, transparent);
  background: color-mix(in srgb, var(--color-warning) 9%, transparent);
  color: var(--color-text-secondary);
}

.knowledge-warning .el-icon {
  flex: 0 0 auto;
  margin-top: 0.08rem;
  color: var(--color-warning);
}

.source-list {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.source-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
  color: var(--color-text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  transition:
    background-color var(--duration-control) var(--ease-standard),
    border-color var(--duration-control) var(--ease-standard);
}

.source-item:hover {
  border-color: var(--color-border);
  background: var(--color-surface-hover);
}

.source-item__icon {
  flex: 0 0 auto;
  color: var(--color-text-muted);
}

.source-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-item__actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex: 0 0 auto;
}

.source-delete {
  width: 36px;
  height: 36px;
  margin: 0;
}

.upload-control {
  display: block;
  margin-top: var(--space-3);
}

.resume-file {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  min-height: 42px;
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
  color: var(--color-text-secondary);
  font-size: var(--font-size-caption);
  font-weight: 500;
}

.resume-file span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.jd-input-area {
  display: grid;
  gap: var(--space-2);
  padding-top: var(--space-3);
  margin-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.jd-input-area__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.jd-input-area__label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--color-text-secondary);
  font-size: var(--font-size-caption);
  font-weight: 500;
}

.jd-input-area :deep(.el-textarea__inner) {
  min-height: 104px;
  border-color: var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
  color: var(--color-text-primary);
}

.jd-input-area :deep(.el-textarea__inner:focus) {
  border-color: var(--color-primary);
  background: var(--color-surface);
  box-shadow: var(--focus-ring-strong);
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  cursor: pointer;
  transition: background-color var(--duration-control) var(--ease-standard);
}

.setting-row:hover {
  background: var(--color-surface-hover);
}

.setting-row__label {
  font-weight: 500;
}

.settings-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.settings-actions .el-button {
  width: 100%;
  min-height: 36px;
  margin: 0;
}

.status-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 40px;
  margin: var(--space-3) 0 0;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.status-dot {
  flex: 0 0 8px;
  width: 8px;
  height: 8px;
  border: 2px solid var(--color-surface);
  border-radius: var(--radius-pill);
  box-shadow: 0 0 0 1px currentColor;
}

.status-on {
  background: var(--color-success);
}

.status-off {
  background: var(--color-danger);
}

.sidebar-account {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 64px;
  padding: var(--space-4) var(--space-2) 0;
  margin-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.sidebar-account__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 36px;
  width: 36px;
  height: 36px;
  border: 1px solid color-mix(in srgb, var(--color-primary) 26%, var(--color-border));
  border-radius: var(--radius-pill);
  background: var(--aurora-gradient-soft);
  color: var(--color-primary);
}

.sidebar-account__identity {
  flex: 1;
}

.sidebar-account__name {
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
  font-weight: 600;
  line-height: var(--line-height-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-account__logout {
  min-height: 36px;
  margin: 0;
}

@media (max-width: 767px) {
  .sidebar-brand {
    min-height: 56px;
    padding: 0 0 var(--space-5);
  }

  .sidebar-home,
  .sidebar-career-link,
  .sidebar-collapse :deep(.el-collapse-item__header),
  .setting-row {
    min-height: 48px;
  }

  .icon-button,
  .source-delete,
  .sidebar-account__logout,
  .settings-actions .el-button,
  .button-stack :deep(.el-button),
  .button-grid :deep(.el-button),
  .upload-control :deep(.el-button) {
    min-width: 44px;
    min-height: 44px;
  }

  .sidebar-collapse :deep(.el-collapse-item__content) {
    padding-right: 0;
    padding-left: var(--space-4);
  }

  .sidebar-account {
    padding: var(--space-4) 0 var(--space-2);
  }
}

@media (prefers-reduced-motion: reduce) {
  .sidebar-close,
  .sidebar-home,
  .sidebar-career-link,
  .sidebar-collapse :deep(.el-collapse-item__header),
  .source-item,
  .setting-row {
    transition-duration: 0.01ms;
  }
}
</style>
