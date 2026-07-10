<template>
  <!-- 欢迎页（未登录） -->
  <WelcomePage
    v-if="!isLoggedIn"
    @login-success="handleLoginSuccess"
  />

  <!-- 主界面（已登录） -->
  <div v-else class="app-container">
    <aside class="sidebar">
      <Sidebar
        ref="sidebarRef"
        :current-username="currentUsername"
        :user-id="currentUserId"
        @session-changed="handleSessionChanged"
        @new-session="handleNewSession"
        @clear-session="handleClearSession"
        @pdf-uploaded="handlePdfUploaded"
        @user-logged-in="handleUserLoggedIn"
        @show-analytics="analyticsPanelRef?.open()"
        @logout="handleLogout"
        @quick-chat="handleQuickChat"
        @go-home="showDashboard = true"
      />
    </aside>
    <main class="chat-area">
      <!-- 工作台首页 -->
      <Dashboard
        v-if="showDashboard"
        :username="currentUsername"
        @action="handleDashboardAction"
      />
      <!-- 对话界面 -->
      <ChatWindow
        v-else
        :messages="messages"
        :session-id="currentSessionId"
        :user-id="currentUserId"
        :quick-text="quickChatText"
        @send-message="handleSendMessage"
        @kb-updated="sidebarRef?.loadDocStatus()"
      />
    </main>

    <AnalyticsPanel ref="analyticsPanelRef" :user-id="currentUserId" />
    <ResumeReport ref="resumeReportRef" :report-text="lastAIResponse" />
    <JobMatchPanel ref="jobMatchPanelRef" :report-text="lastAIResponse" />
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import WelcomePage from './components/WelcomePage.vue'
import Sidebar from './components/Sidebar.vue'
import ChatWindow from './components/ChatWindow.vue'
import AnalyticsPanel from './components/AnalyticsPanel.vue'
import ResumeReport from './components/ResumeReport.vue'
import JobMatchPanel from './components/JobMatchPanel.vue'
import Dashboard from './components/Dashboard.vue'
import { getMessages } from './api'

const isLoggedIn = ref(false)
const currentUsername = ref('')
const messages = ref([])
const currentSessionId = ref(null)
const currentUserId = ref(null)
const sidebarRef = ref(null)
const analyticsPanelRef = ref(null)
const resumeReportRef = ref(null)
const jobMatchPanelRef = ref(null)

// 工作台 / 对话切换
const showDashboard = ref(true)
const initialSessionReady = ref(false)  // 标记侧边栏是否已完成首次会话初始化

// 跟踪最新 AI 回复，供报告面板使用
const lastAIResponse = ref('')

// 工作台卡片点击 → 切换到对话并触发快捷操作
const handleDashboardAction = (intent) => {
  showDashboard.value = false
  lastQuickIntent.value = intent
  quickChatText.value = intent + ' '
  nextTick(() => { quickChatText.value = '' })
}

const handleLoginSuccess = (userId, username) => {
  currentUserId.value = userId
  currentUsername.value = username
  isLoggedIn.value = true
}

const handleLogout = () => {
  localStorage.removeItem('ai_user_id')
  localStorage.removeItem('ai_username')
  isLoggedIn.value = false
  currentUserId.value = null
  currentUsername.value = ''
  messages.value = []
  currentSessionId.value = null
  showDashboard.value = true
  initialSessionReady.value = false
}

onMounted(() => {
  const savedId = localStorage.getItem('ai_user_id')
  const savedName = localStorage.getItem('ai_username')
  if (savedId && savedName) {
    currentUserId.value = parseInt(savedId)
    currentUsername.value = savedName
    isLoggedIn.value = true
  }
})

const handleSessionChanged = async (sessionId) => {
  currentSessionId.value = sessionId
  // 首次自动初始化时不跳转，停留在工作台
  if (!initialSessionReady.value) {
    initialSessionReady.value = true
    return
  }
  showDashboard.value = false
  try {
    const res = await getMessages(sessionId)
    messages.value = res.data.map(m => ({
      role: m.role, content: m.content, id: m.id,
      feedback: m.feedback, timestamp: m.timestamp
    }))
  } catch (e) { messages.value = [] }
}

const handleNewSession = (sessionId) => {
  currentSessionId.value = sessionId; messages.value = []
  if (!initialSessionReady.value) { initialSessionReady.value = true; return }
  showDashboard.value = false
}
const handleClearSession = () => { currentSessionId.value = null; messages.value = []; showDashboard.value = true }
const handlePdfUploaded = () => {}
const handleSendMessage = (newMessages) => {
  messages.value = [...messages.value, ...newMessages]
  // 捕获最新 AI 回复
  const last = newMessages[newMessages.length - 1]
  if (last && last.role === 'assistant') {
    lastAIResponse.value = last.content
  }
}
const handleUserLoggedIn = (id) => { currentUserId.value = id }

const quickChatText = ref('')
const lastQuickIntent = ref('')  // 记录最近一次快捷操作类型
const handleQuickChat = (text) => {
  lastQuickIntent.value = text
  quickChatText.value = text + ' '
  nextTick(() => { quickChatText.value = '' })
}

// AI回复后自动打开对应面板
watch(lastAIResponse, (val) => {
  if (!val || !lastQuickIntent.value) return
  const intent = lastQuickIntent.value
  lastQuickIntent.value = ''
  if (intent.includes('分析简历') || val.includes('综合评分')) {
    nextTick(() => resumeReportRef.value?.open())
  } else if (intent.includes('匹配') || val.includes('匹配度')) {
    nextTick(() => jobMatchPanelRef.value?.open())
  }
})


</script>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  background: #f5f6fa;
}
.sidebar {
  width: 330px;
  background: #fff;
  border-right: 1.5px solid #eef0f6;
  padding: 16px 18px;
  overflow-y: auto;
  box-shadow: 2px 0 16px rgba(0,0,0,0.03);
}
.sidebar::-webkit-scrollbar { width: 5px; }
.sidebar::-webkit-scrollbar-thumb { background: #d0d5e0; border-radius: 3px; }
.sidebar::-webkit-scrollbar-track { background: transparent; }
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
</style>

<!-- 暗色模式全局样式 -->
<style>
html.dark body {
  background: #1a1a2e;
}
html.dark .app-container {
  background: #1a1a2e;
}
html.dark .sidebar {
  background: #16213e;
  border-color: #2a2a4a;
}
html.dark .sidebar h2,
html.dark .sidebar .user-name,
html.dark .sidebar .source-list-label {
  color: #e0e0e0;
}
html.dark .chat-container {
  background: #1a1a2e;
}
html.dark .message-list {
  background: #1a1a2e;
}
html.dark .bubble--bot {
  background: #2a2a4a;
  color: #e0e0e0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}
html.dark .input-area {
  background: #16213e;
  border-color: #2a2a4a;
}
html.dark .source-item {
  color: #aaa;
  border-color: #2a2a4a;
}
html.dark .setting-row {
  color: #e0e0e0;
}
html.dark .status-bar {
  color: #aaa;
}
html.dark .msg-time {
  color: #777;
}
html.dark .source-label,
html.dark .typing-indicator {
  color: #888;
}
html.dark .welcome-container {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
}
html.dark .welcome-card {
  background: #16213e;
}
html.dark .form-side h2 {
  color: #e0e0e0;
}
html.dark .form-sub {
  color: #999;
}
html.dark .demo-hint {
  color: #666;
}
html.dark .toggle-text {
  color: #999;
}
html.dark .greeting { color: #e0e0e0; }
html.dark .feature-card { background: #16213e; border-color: #2a2a4a; }
html.dark .feature-card h3 { color: #e0e0e0; }
html.dark .tips-section { background: #16213e; border-color: #2a2a4a; }
html.dark .tips-title { color: #e0e0e0; }
html.dark .tip-item { background: #1a1a2e; }
html.dark .tip-item strong { color: #ccc; }
html.dark .home-btn { background: #1a1a2e; border-color: #2a2a4a; color: #8899ff; }
html.dark .home-btn:hover { border-color: #5b7fff; background: #1e1e3a; }
</style>