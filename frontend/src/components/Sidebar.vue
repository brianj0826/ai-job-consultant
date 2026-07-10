<template>
  <div>
    <h2>💼 职达求职顾问</h2>

    <!-- 用户信息 -->
    <div class="user-info-bar">
      <span class="user-avatar">👤</span>
      <span class="user-name">{{ currentUsername || '未登录' }}</span>
      <el-button
        @click="$emit('logout')"
        type="danger"
        size="small"
        plain
        class="logout-btn"
      >
        退出
      </el-button>
    </div>

    <el-button @click="$emit('go-home')" size="small" class="home-btn">🏠 首页工作台</el-button>

    <el-collapse v-model="activePanels" class="sidebar-collapse">
      <!-- 会话管理 -->
      <el-collapse-item title="💬 会话管理" name="chat">
        <div style="display: flex; gap: 6px; margin-bottom: 8px;">
          <el-select v-model="currentSessionId" placeholder="选择会话" @change="switchSession" style="flex: 1;" size="small">
            <el-option v-for="s in sessions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <el-button @click="handleRenameSession" size="small" :disabled="!currentSessionId" title="重命名">✏️</el-button>
        </div>
        <div class="btn-stack">
          <el-button type="primary" @click="newSession" size="small" style="width:100%">➕ 新建对话</el-button>
          <el-button @click="clearSession" type="danger" plain size="small" style="width:100%">🗑️ 清空</el-button>
          <div style="display:flex;gap:6px">
            <el-button @click="exportSession" size="small" style="flex:1">📥 导出</el-button>
            <el-button @click="$emit('show-analytics')" type="warning" size="small" style="flex:1">📊 数据</el-button>
          </div>
        </div>
      </el-collapse-item>

      <!-- 知识库 -->
      <el-collapse-item title="📚 知识库" name="kb">
        <el-tag v-if="docCount > 0" type="success" size="small">✅ {{ docCount }} 个文档块</el-tag>
        <el-tag v-else type="warning" size="small">⚠️ 为空，请上传文档</el-tag>
        <div v-if="docSources.length" style="margin-top:6px">
          <div v-for="(s, i) in docSources" :key="i" class="source-item">
            <span :title="s.source" class="source-name">{{ s.source.length > 25 ? s.source.slice(0,25)+'...' : s.source }}</span>
            <div style="display:flex;align-items:center;gap:4px">
              <el-tag :type="s.type==='web'?'warning':'info'" size="small">{{ s.type==='web'?'🌐':'📄' }}</el-tag>
              <el-button @click="handleDeleteSource(s.source)" type="danger" size="small" circle :loading="deletingSource===s.source"><el-icon><Delete /></el-icon></el-button>
            </div>
          </div>
        </div>
        <el-upload :http-request="uploadFile" :show-file-list="false" accept=".pdf,.txt,.md,.docx" style="margin-top:8px">
          <el-button type="primary" plain size="small" style="width:100%">📤 上传文档</el-button>
        </el-upload>
      </el-collapse-item>

      <!-- 求职工具箱 -->
      <el-collapse-item title="🔧 求职工具箱" name="career" v-if="docSources.length">
        <div class="resume-file" v-if="resumeSource">📋 {{ resumeSource.title || resumeSource.source }}</div>
        <div class="tool-btns">
          <el-button @click="$emit('quick-chat','帮我分析一下我的简历')" type="primary" size="small" :disabled="!resumeSource" style="flex:1">🔍 分析</el-button>
          <el-button @click="$emit('quick-chat','请帮我模拟面试，先问我的目标岗位，然后逐题提问并点评')" type="success" size="small" style="flex:1">🎤 面试</el-button>
        </div>
        <div class="jd-input-area">
          <div style="display:flex;align-items:center;gap:4px;margin-bottom:4px">
            <span style="font-size:12px;color:#909399">📋 岗位JD</span>
            <el-button @click="handleFetchJD" size="small" :loading="fetchingJD" style="margin-left:auto;font-size:11px">🔗 链接导入</el-button>
          </div>
          <el-input v-model="jdText" type="textarea" :rows="5" placeholder="粘贴岗位JD..." size="small" />
          <div class="jd-btns">
            <el-button @click="handleMatchJob" type="success" size="small" :disabled="!jdText||!resumeSource" style="flex:1">🎯 匹配</el-button>
            <el-button @click="handleGenQuestions" type="warning" size="small" :disabled="!jdText" style="flex:1">💬 出题</el-button>
          </div>
        </div>
      </el-collapse-item>

      <!-- 设置 -->
      <el-collapse-item title="⚙️ 设置" name="settings">
        <div class="setting-row">
          <span>🌓 暗色模式</span>
          <el-switch v-model="isDark" @change="toggleDark" size="small" />
        </div>
        <div class="status-bar">
          <span :class="['status-dot', backendOnline?'status-on':'status-off']"></span>
          <span class="status-text">{{ backendOnline?'服务正常':'服务离线' }}</span>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import {
  getSessions, createSession, deleteSession, renameSession,
  getMessages, uploadPDF, getDocStatus, deleteSource, fetchUrlContent
} from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'

const props = defineProps({
  currentUsername: { type: String, default: '' },
  userId: { type: Number, default: null }
})

const emit = defineEmits(['session-changed', 'new-session', 'clear-session', 'pdf-uploaded', 'user-logged-in', 'show-analytics', 'logout', 'quick-chat', 'go-home'])

// 寻找简历文件（第一个非网页来源的文档）
const resumeSource = computed(() => {
  return docSources.value.find(s => s.type === 'file') || null
})

const activePanels = ref(['chat'])  // 默认展开会话管理
const sessions = ref([])
const currentSessionId = ref(null)
const recentMessages = ref([])
const docCount = ref(0)
const docSources = ref([])
const deletingSource = ref(null)
const jdText = ref('')
const fetchingJD = ref(false)

const handleMatchJob = () => {
  if (!jdText.value) return
  const msg = '请根据以下岗位JD，帮我匹配我的简历：\n\n' + jdText.value
  emit('quick-chat', msg)
}

// 从URL抓取JD内容填入输入框
const handleFetchJD = async () => {
  try {
    const { value: url } = await ElMessageBox.prompt('请输入招聘页面的URL', '链接导入JD', {
      confirmButtonText: '抓取', cancelButtonText: '取消',
      inputPlaceholder: 'https://www.zhipin.com/...'
    })
    if (!url || !url.trim()) return
    fetchingJD.value = true
    const res = await fetchUrlContent(url.trim())
    const title = res.data.title || ''
    const text = res.data.text || ''
    jdText.value = (title ? '【' + title + '】\n' : '') + text
    ElMessage.success('JD内容已导入')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('抓取失败，请检查URL是否正确')
  } finally {
    fetchingJD.value = false
  }
}

const handleGenQuestions = () => {
  if (!jdText.value) return
  const msg = '请根据以下岗位JD生成5道面试题：\n\n' + jdText.value
  emit('quick-chat', msg)
}

// 当 userId 变化时（登录后），自动加载
const initUserData = async () => {
  if (!props.userId) return
  currentSessionId.value = null
  recentMessages.value = []
  docSources.value = []

  await loadSessions()
  await loadDocStatus()

  if (sessions.value.length === 0) {
    const now = new Date()
    const name = `${now.toLocaleDateString()} ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    const newRes = await createSession(props.userId, name)
    currentSessionId.value = newRes.data.session_id
    emit('new-session', currentSessionId.value)
    await loadSessions()
    switchSession(currentSessionId.value)
  } else {
    currentSessionId.value = sessions.value[0].id
    switchSession(currentSessionId.value)
  }
}

watch(() => props.userId, (newVal) => {
  if (newVal) initUserData()
})

// 加载会话列表
const loadSessions = async () => {
  if (!props.userId) return
  const res = await getSessions(props.userId)
  sessions.value = res.data
  if (sessions.value.length && !currentSessionId.value) {
    currentSessionId.value = sessions.value[0].id
    switchSession(currentSessionId.value)
  }
}

// 切换会话
const switchSession = async (sessionId) => {
  emit('session-changed', sessionId)
  try {
    const res = await getMessages(sessionId)
    recentMessages.value = res.data.slice(-5)
  } catch (e) {
    recentMessages.value = []
  }
}

// 新建会话
const newSession = async () => {
  if (!props.userId) return
  const now = new Date()
  const name = `${now.toLocaleDateString()} ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
  const res = await createSession(props.userId, name)
  currentSessionId.value = res.data.session_id
  emit('new-session', currentSessionId.value)
  await loadSessions()
  switchSession(currentSessionId.value)
}

// 清空会话
const clearSession = async () => {
  if (!currentSessionId.value) return
  try {
    await ElMessageBox.confirm(
      '确定要清空当前会话吗？所有对话记录将被永久删除。',
      '确认清空',
      { confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteSession(currentSessionId.value)
    emit('clear-session')
    await loadSessions()
    if (sessions.value.length) {
      currentSessionId.value = sessions.value[0].id
      switchSession(currentSessionId.value)
    } else {
      currentSessionId.value = null
      recentMessages.value = []
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('清空会话失败')
    }
  }
}

// 导出对话
const exportSession = async () => {
  if (!currentSessionId.value) {
    ElMessage.warning('请先选择会话')
    return
  }
  try {
    const res = await getMessages(currentSessionId.value)
    const msgs = res.data
    if (!msgs.length) {
      ElMessage.info('当前没有对话记录')
      return
    }
    let text = ''
    msgs.forEach(m => {
      text += `${m.role === 'user' ? '用户' : '助手'}：${m.content}\n\n`
    })
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `对话记录_${new Date().toLocaleString()}.txt`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败')
  }
}

// 上传文档（支持 PDF / TXT / MD / DOCX）
const uploadFile = async (option) => {
  const file = option.file
  const alreadyExists = docSources.value.some(s => s.source === file.name)
  if (alreadyExists) {
    ElMessage.info('该文件已在当前知识库中，无需重复上传')
    return
  }

  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('user_id', props.userId)
    const res = await uploadPDF(formData)

    // 无论后台还是同步，只要状态码 200 就视为成功
    if (res.status === 200) {
      // 立刻刷新知识库来源列表
      ElMessage.success(res.data.message || '文档上传成功，知识库已更新')
      emit('pdf-uploaded')

      // 异步刷新知识库状态（不阻塞 UI）
      loadDocStatus()

      // 如果有当前会话，重新加载消息（但不强制等待）
      if (currentSessionId.value) {
        switchSession(currentSessionId.value)
      }
    } else {
      ElMessage.error('上传返回异常状态')
    }
  } catch (e) {
    console.error('上传失败详情:', e)
    ElMessage.error('上传失败，请稍后重试')
  }
}

// 查询文档数量（传入 userId）
const loadDocStatus = async () => {
  try {
    const res = await getDocStatus(props.userId)
    docCount.value = res.data.doc_count
    docSources.value = res.data.sources || []
  } catch (e) {
    docCount.value = 0
    docSources.value = []
  }
}

// 暴露给父组件调用
defineExpose({ loadDocStatus })

// 暗色模式
const isDark = ref(false)
const toggleDark = () => {
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('ai_dark_mode', isDark.value ? '1' : '0')
}

// 会话重命名
const handleRenameSession = async () => {
  if (!currentSessionId.value) return
  try {
    const { value } = await ElMessageBox.prompt('请输入新名称', '重命名会话', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: sessions.value.find(s => s.id === currentSessionId.value)?.name || ''
    })
    if (value && value.trim()) {
      await renameSession(currentSessionId.value, value.trim())
      ElMessage.success('已重命名')
      await loadSessions()
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('重命名失败')
  }
}

// 系统状态检测
const backendOnline = ref(true)
let statusTimer = null
const checkBackendStatus = async () => {
  try {
    const res = await fetch('/api/analytics/overview', { signal: AbortSignal.timeout(5000) })
    backendOnline.value = res.ok
  } catch {
    backendOnline.value = false
  }
}

// 删除知识库来源
const handleDeleteSource = async (source) => {
  if (!props.userId) return
  try {
    await ElMessageBox.confirm(
      `确定要删除来源「${source}」的所有内容吗？此操作不可恢复。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    deletingSource.value = source
    await deleteSource(props.userId, source)
    ElMessage.success('已删除')
    await loadDocStatus()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  } finally {
    deletingSource.value = null
  }
}

onMounted(() => {
  if (props.userId) initUserData()
  // 初始化暗色模式状态
  isDark.value = document.documentElement.classList.contains('dark')
  // 启动系统状态检测
  checkBackendStatus()
  statusTimer = setInterval(checkBackendStatus, 30000)
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
})
</script>

<style scoped>
/* ============ 首页按钮 ============ */
.home-btn { width:100%; margin-bottom:8px; background: linear-gradient(135deg, #f0f4ff, #f8f0ff); border: 1.5px solid #e0e4f0; color: #5b7fff; font-weight: 600; }
.home-btn:hover { border-color: #5b7fff; background: linear-gradient(135deg, #e8edff, #f0e8ff); }

/* ============ 用户栏 ============ */
.user-info-bar { display: flex; align-items: center; gap: 10px; padding: 10px 12px; background: #f8f9fd; border-radius: 12px; margin-bottom: 4px; }
.user-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, #5b7fff, #6c5ce7);
  display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0;
}
.user-name { flex: 1; font-weight: 600; color: #303133; font-size: 14px; }
.logout-btn { flex-shrink: 0; font-size: 12px; }

/* ============ 折叠面板 ============ */
.sidebar-collapse { border: none; }
.sidebar-collapse :deep(.el-collapse-item) { margin-bottom: 2px; }
.sidebar-collapse :deep(.el-collapse-item__header) {
  font-size: 13px; font-weight: 600; border: none;
  padding: 10px 12px; border-radius: 10px;
  color: #444; background: transparent;
  transition: all 0.2s ease;
}
.sidebar-collapse :deep(.el-collapse-item__header:hover) { background: #f5f7fc; color: #5b7fff; }
.sidebar-collapse :deep(.el-collapse-item__wrap) { border: none; background: transparent; }
.sidebar-collapse :deep(.el-collapse-item__content) { padding: 6px 4px 14px; }

/* ============ 按钮组 ============ */
.btn-stack { display: flex; flex-direction: column; gap: 6px; }
.btn-stack .el-button { border-radius: 10px; transition: all 0.2s ease; }
.btn-stack .el-button:hover { transform: translateY(-1px); }

/* ============ 来源项 ============ */
.source-item {
  display: flex; align-items: center; justify-content: space-between;
  gap: 4px; padding: 6px 8px; font-size: 11px; color: #606266;
  border-radius: 8px; margin-bottom: 2px;
  transition: all 0.2s ease;
}
.source-item:hover { background: #f5f7fc; }
.source-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }

/* ============ 设置行 ============ */
.setting-row { display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; font-size: 13px; border-radius: 8px; }
.setting-row:hover { background: #f5f7fc; }

/* ============ 状态栏 ============ */
.status-bar { display: flex; align-items: center; gap: 6px; padding: 8px; font-size: 12px; color: #909399; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-on { background: #67C23A; box-shadow: 0 0 6px rgba(103,194,58,0.4); }
.status-off { background: #F56C6C; box-shadow: 0 0 6px rgba(245,108,108,0.4); }

/* ============ 求职工具箱 ============ */
.resume-file {
  padding: 8px 12px; background: linear-gradient(135deg, #ecf5ff, #e8f0fe);
  border-radius: 10px; margin-bottom: 10px; font-size: 12px; color: #409EFF;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 500; border: 1px solid #d9e8ff;
}
.tool-btns { display: flex; gap: 6px; }
.jd-input-area { margin-top: 10px; }
.jd-input-area :deep(.el-textarea__inner) { border-radius: 10px; font-size: 12px; border-color: #e8ecf2; background: #fafbfc; transition: all 0.2s; }
.jd-input-area :deep(.el-textarea__inner:focus) { border-color: #5b7fff; box-shadow: 0 0 0 2px rgba(91,127,255,0.08); background: #fff; }
.jd-btns { display: flex; gap: 6px; margin-top: 8px; }
</style>