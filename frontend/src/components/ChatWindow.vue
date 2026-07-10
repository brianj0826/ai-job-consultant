<template>
  <section class="chat-container" aria-label="AI 求职顾问对话" :aria-busy="ariaBusy ? 'true' : 'false'">
    <div class="conversation-region">
      <div
        ref="msgListRef"
        class="message-list"
        role="log"
        aria-live="off"
        aria-relevant="additions"
        :aria-busy="ariaBusy ? 'true' : 'false'"
        @scroll.passive="handleMessageScroll"
      >
        <TransitionGroup
          tag="div"
          name="message"
          class="message-stack"
          :class="{ 'message-stack--hydrating': hydratingHistory }"
          :css="!hydratingHistory"
        >
          <div
            v-if="isSessionLoading && showSessionSkeleton"
            key="session-loading"
            class="session-skeleton"
            data-testid="session-skeleton"
            role="status"
          >
            <span class="sr-only">正在加载会话记录</span>
            <div v-for="index in 3" :key="index" class="session-skeleton__row" aria-hidden="true">
              <span class="session-skeleton__avatar"></span>
              <span class="session-skeleton__bubble">
                <span></span>
                <span></span>
                <span></span>
              </span>
            </div>
          </div>

          <div
            v-else-if="hasSessionError"
            key="session-error"
            class="session-error-state"
            data-testid="session-error"
            role="alert"
          >
            <el-icon class="state-icon" aria-hidden="true"><WarningFilled /></el-icon>
            <div>
              <strong>会话记录加载失败</strong>
              <p>{{ sessionError || '暂时无法读取当前会话，请稍后重试。' }}</p>
              <el-button size="small" plain @click="retrySession">
                <el-icon aria-hidden="true"><RefreshRight /></el-icon>
                重新加载
              </el-button>
            </div>
          </div>

          <div
            v-else-if="conversationReady && !messages.length && !activeReplyVisible"
            key="chat-empty"
            class="chat-empty-state"
          >
            <div class="empty-icon" aria-hidden="true">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <p class="technical-label">CAREER INTELLIGENCE</p>
            <h2>{{ emptyStateTitle }}</h2>
            <p>{{ emptyStateDescription }}</p>
          </div>

          <MessageBubble
            v-for="(message, index) in visibleMessages"
            :key="messageKey(message, index)"
            v-memo="[message.content, message.feedback, currentFeedback(message)]"
            :message="message"
            :feedback-value="currentFeedback(message)"
            @feedback="feedback"
          />

          <MessageBubble
            v-if="conversationReady && activeReplyVisible"
            :key="activeStreamKey"
            :message="activeMessage"
            :rendered-html="streamRendered"
            :streaming="streaming"
            :interrupted="interrupted"
            :error="connectionError"
            @retry="retryLastMessage"
          />

          <div
            v-if="conversationReady && standaloneError"
            key="composer-error"
            class="chat-error-state"
            role="alert"
          >
            <el-icon class="state-icon" aria-hidden="true"><WarningFilled /></el-icon>
            <div>
              <strong>暂时无法发送</strong>
              <p>{{ standaloneError }}</p>
            </div>
          </div>
        </TransitionGroup>
      </div>

      <Transition name="jump-latest">
        <el-button
          v-if="showBackToLatest"
          class="back-to-latest"
          size="small"
          round
          @click="goToLatest"
        >
          <el-icon aria-hidden="true"><ArrowDown /></el-icon>
          回到最新
        </el-button>
      </Transition>
    </div>

    <p class="sr-only" aria-live="polite" aria-atomic="true">{{ finalAnnouncement }}</p>

    <form class="input-area" @submit.prevent="send">
      <div class="input-shell">
        <label class="sr-only" for="chat-message-input">向职达 AI 提问</label>
        <el-input
          id="chat-message-input"
          v-model="input"
          class="input-field"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 5 }"
          placeholder="描述你的求职问题，或粘贴一段职位描述…"
          :disabled="composerDisabled"
          @keydown.enter.exact.prevent="send"
        />
        <el-button
          class="send-button"
          native-type="submit"
          type="primary"
          :disabled="!input.trim() || composerDisabled"
          :loading="streaming"
          aria-label="发送消息"
        >
          <el-icon v-if="!streaming"><ArrowUp /></el-icon>
          <span>发送</span>
        </el-button>
      </div>
      <p class="input-helper">
        <span v-if="streaming">AI 正在生成回复，请稍候。</span>
        <span v-else-if="isSessionLoading">正在载入当前会话。</span>
        <span v-else>按 Enter 发送，Shift + Enter 换行。</span>
      </p>
    </form>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowDown,
  ArrowUp,
  ChatDotRound,
  RefreshRight,
  WarningFilled
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { submitFeedback } from '../api'
import { useStreamingBuffer } from '../composables/useStreamingBuffer'
import MessageBubble from './MessageBubble.vue'

const SESSION_SKELETON_DELAY = 150
const AUTO_FOLLOW_THRESHOLD = 80

const props = defineProps({
  messages: { type: Array, default: () => [] },
  sessionId: Number,
  userId: Number,
  quickText: { type: String, default: '' },
  sessionStatus: {
    type: String,
    default: 'ready',
    validator: (value) => ['idle', 'loading', 'ready', 'error'].includes(value)
  },
  sessionError: { type: String, default: '' }
})

const emit = defineEmits(['send-message', 'kb-updated', 'retry-session'])

const input = ref('')
const msgListRef = ref(null)
const streaming = ref(false)
const interrupted = ref(false)
const connectionError = ref('')
const standaloneError = ref('')
const lastRequest = ref('')
const localFeedback = ref({})
const activeStreamKey = ref('stream-0')
const finalAnnouncement = ref('')
const isNearBottom = ref(true)
const hydratingHistory = ref(true)
const showSessionSkeleton = ref(false)

let streamSequence = 0
let scrollFrame = null
let scrollForce = false
let hydrationFrame = null
let skeletonTimer = null

const cleanSourceMarkers = (text) => text?.replace(/【来源\d+[^】]*】/g, '') || ''
const renderStreamingMarkdown = (text) => (
  text ? DOMPurify.sanitize(marked(cleanSourceMarkers(text))) : ''
)

const {
  append: appendStreamToken,
  beginReplacement,
  flush: flushStream,
  rendered: streamRendered,
  reset: resetStream,
  text: streamText
} = useStreamingBuffer({ render: renderStreamingMarkdown })

const isSessionLoading = computed(() => props.sessionStatus === 'loading')
const hasSessionError = computed(() => props.sessionStatus === 'error')
const conversationReady = computed(() => !isSessionLoading.value && !hasSessionError.value)
const composerDisabled = computed(() => streaming.value || isSessionLoading.value || hasSessionError.value)
const ariaBusy = computed(() => streaming.value || isSessionLoading.value)
const activeReplyVisible = computed(() => streaming.value || interrupted.value)
const visibleMessages = computed(() => conversationReady.value ? props.messages : [])
const activeMessage = computed(() => ({
  role: 'assistant',
  content: streamText.value,
  timestamp: ''
}))

const emptyStateTitle = computed(() => (
  props.sessionId ? '开始你的职业对话' : '选择一个会话后开始对话'
))
const emptyStateDescription = computed(() => (
  props.sessionId
    ? '可以分析简历、比对岗位要求，或准备下一场面试。'
    : '从左侧新建或选择会话，职达 AI 会在这里保留完整上下文。'
))

const messageKey = (message, index) => (
  message._clientKey || message.id || `${message.role}-${message.timestamp || index}-${index}`
)

const requestFrame = (callback) => (
  typeof window.requestAnimationFrame === 'function'
    ? window.requestAnimationFrame(callback)
    : window.setTimeout(callback, 16)
)
const cancelFrame = (frame) => {
  if (frame === null) return
  if (typeof window.cancelAnimationFrame === 'function') window.cancelAnimationFrame(frame)
  else window.clearTimeout(frame)
}

const distanceFromBottom = (element) => Math.max(
  0,
  element.scrollHeight - element.scrollTop - element.clientHeight
)

const handleMessageScroll = () => {
  if (!msgListRef.value) return
  isNearBottom.value = distanceFromBottom(msgListRef.value) <= AUTO_FOLLOW_THRESHOLD
}

const scheduleScrollToBottom = ({ force = false } = {}) => {
  scrollForce = scrollForce || force
  if (scrollFrame !== null) return

  scrollFrame = requestFrame(() => {
    scrollFrame = null
    const shouldScroll = scrollForce || isNearBottom.value
    scrollForce = false
    if (!shouldScroll || !msgListRef.value) return
    msgListRef.value.scrollTop = msgListRef.value.scrollHeight
    isNearBottom.value = true
  })
}

const goToLatest = () => {
  isNearBottom.value = true
  scheduleScrollToBottom({ force: true })
}

const showBackToLatest = computed(() => (
  conversationReady.value
  && !isNearBottom.value
  && (props.messages.length > 0 || activeReplyVisible.value)
))

const finishHistoryHydration = () => {
  cancelFrame(hydrationFrame)
  hydrationFrame = requestFrame(() => {
    hydrationFrame = null
    hydratingHistory.value = false
    scheduleScrollToBottom({ force: true })
  })
}

const beginHistoryHydration = () => {
  cancelFrame(hydrationFrame)
  hydrationFrame = null
  hydratingHistory.value = true
}

const syncSessionState = (status) => {
  if (skeletonTimer !== null) {
    clearTimeout(skeletonTimer)
    skeletonTimer = null
  }

  if (status === 'loading') {
    beginHistoryHydration()
    showSessionSkeleton.value = false
    skeletonTimer = setTimeout(() => {
      skeletonTimer = null
      if (props.sessionStatus === 'loading') showSessionSkeleton.value = true
    }, SESSION_SKELETON_DELAY)
    return
  }

  showSessionSkeleton.value = false
  nextTick(finishHistoryHydration)
}

const send = () => {
  const text = input.value.trim()
  if (!text || composerDisabled.value) return

  if (!props.sessionId || !props.userId) {
    standaloneError.value = '请先登录并选择一个会话后再发送消息。'
    ElMessage.warning('请先登录并选择会话')
    return
  }

  input.value = ''
  requestReply(text, true, false)
}

const retryLastMessage = () => {
  if (!lastRequest.value || streaming.value) return
  if (!props.sessionId || !props.userId) {
    connectionError.value = '当前会话不可用，请重新选择会话后再尝试。'
    interrupted.value = true
    return
  }
  requestReply(lastRequest.value, false, true)
}

const requestReply = async (text, shouldEmitUser, reuseBubble) => {
  connectionError.value = ''
  standaloneError.value = ''
  finalAnnouncement.value = ''
  lastRequest.value = text

  if (reuseBubble) {
    beginReplacement()
  } else {
    streamSequence += 1
    activeStreamKey.value = `stream-${streamSequence}`
    resetStream()
  }

  interrupted.value = false
  streaming.value = true

  if (shouldEmitUser) {
    emit('send-message', [{
      role: 'user',
      content: text,
      timestamp: new Date().toISOString()
    }])
  }

  scheduleScrollToBottom({ force: true })

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        user_id: props.userId,
        session_id: props.sessionId
      })
    })

    if (!response.ok) {
      let detail = ''
      try {
        const errorData = await response.json()
        detail = errorData.detail || ''
      } catch {
        // Keep the generic response failure message below.
      }
      throw new Error(detail || '请求失败，请稍后重试。')
    }

    if (!response.body) throw new Error('连接未返回可读取的回复内容。')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalData = null

    const processEventLine = (line) => {
      if (!line.startsWith('data: ')) return
      try {
        const data = JSON.parse(line.slice(6))
        if (data.token) appendStreamToken(data.token)
        else if (data.done) finalData = data
        else if (data.error) throw new Error(data.error)
      } catch (error) {
        if (error instanceof SyntaxError) return
        throw error
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      lines.forEach(processEventLine)
    }

    buffer += decoder.decode()
    if (buffer) buffer.split('\n').forEach(processEventLine)

    if (!finalData?.done) throw new Error('连接已中断，未收到完整回复。')

    const finalText = flushStream()
    const aiMessage = {
      role: 'assistant',
      content: finalText,
      id: finalData.msg_id || null,
      sources: finalData.sources || [],
      timestamp: new Date().toISOString(),
      _clientKey: activeStreamKey.value
    }

    emit('send-message', [aiMessage])
    if (aiMessage.sources.length) emit('kb-updated')
    lastRequest.value = ''
    interrupted.value = false
    streaming.value = false
    nextTick(() => {
      finalAnnouncement.value = '职达 AI 的回复已完成。'
      scheduleScrollToBottom()
    })
  } catch (error) {
    flushStream()
    connectionError.value = error instanceof Error
      ? error.message
      : '连接失败，请稍后重试。'
    interrupted.value = true
  } finally {
    streaming.value = false
    scheduleScrollToBottom()
  }
}

const currentFeedback = (message) => localFeedback.value[message.id] ?? message.feedback

const feedback = async (messageId, type) => {
  try {
    await submitFeedback(messageId, type)
    localFeedback.value = { ...localFeedback.value, [messageId]: type }
    ElMessage.success('感谢你的反馈')
  } catch {
    ElMessage.error('反馈提交失败，请稍后再试')
  }
}

const retrySession = () => emit('retry-session', props.sessionId)

watch(() => props.quickText, (text) => {
  if (!text) return
  input.value = text.trim()
  nextTick(send)
}, { immediate: true })

watch(() => props.sessionId, () => {
  beginHistoryHydration()
  if (!isSessionLoading.value) nextTick(finishHistoryHydration)
})

watch(() => props.sessionStatus, syncSessionState, { immediate: true })

watch(() => props.messages, () => {
  nextTick(() => scheduleScrollToBottom({ force: hydratingHistory.value }))
})

watch(streamRendered, () => scheduleScrollToBottom())

onMounted(() => {
  handleMessageScroll()
  if (!isSessionLoading.value) finishHistoryHydration()
})

onBeforeUnmount(() => {
  cancelFrame(scrollFrame)
  cancelFrame(hydrationFrame)
  if (skeletonTimer !== null) clearTimeout(skeletonTimer)
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: var(--color-canvas);
}

.conversation-region {
  position: relative;
  flex: 1;
  min-height: 0;
}

.message-list {
  height: 100%;
  overflow-y: auto;
  padding: var(--space-8) var(--page-padding) var(--space-4);
}

.message-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  min-height: 100%;
}

.chat-empty-state {
  display: grid;
  place-items: center;
  align-self: center;
  max-width: 34rem;
  min-height: 100%;
  padding: var(--space-12) var(--space-6);
  color: var(--color-text-secondary);
  text-align: center;
}

.empty-icon {
  display: grid;
  width: 3.5rem;
  height: 3.5rem;
  margin-bottom: var(--space-5);
  place-items: center;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-panel);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 1.5rem;
}

.chat-empty-state .technical-label {
  margin-bottom: var(--space-2);
}

.chat-empty-state h2 {
  margin-bottom: var(--space-2);
  font-size: var(--font-size-section-title);
  line-height: var(--line-height-section-title);
}

.chat-empty-state p:last-child {
  max-width: 30rem;
  margin: 0;
  line-height: var(--line-height-body-large);
}

.session-skeleton {
  display: grid;
  align-content: start;
  gap: var(--space-6);
  width: min(100%, var(--chat-max-width));
}

.session-skeleton__row {
  display: flex;
  gap: var(--space-3);
  width: min(100%, 42rem);
}

.session-skeleton__row:nth-child(even) {
  align-self: flex-end;
  width: min(72%, 34rem);
  flex-direction: row-reverse;
}

.session-skeleton__avatar,
.session-skeleton__bubble span {
  background: linear-gradient(
    100deg,
    var(--color-surface-subtle) 20%,
    var(--color-surface-hover) 45%,
    var(--color-surface-subtle) 70%
  );
  background-size: 220% 100%;
  animation: skeleton-shimmer 1.4s ease-in-out infinite;
}

.session-skeleton__avatar {
  width: 2rem;
  height: 2rem;
  flex: 0 0 auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
}

.session-skeleton__bubble {
  display: grid;
  flex: 1;
  gap: var(--space-3);
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface);
}

.session-skeleton__bubble span {
  height: .7rem;
  border-radius: var(--radius-pill);
}

.session-skeleton__bubble span:nth-child(2) {
  width: 88%;
}

.session-skeleton__bubble span:nth-child(3) {
  width: 62%;
}

.session-error-state,
.chat-error-state {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  align-self: center;
  width: min(100%, var(--chat-max-width));
  padding: var(--space-4);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-card);
  background: var(--color-danger-soft);
  color: var(--color-text-primary);
}

.session-error-state {
  margin: auto 0;
}

.state-icon {
  flex: 0 0 auto;
  margin-top: .1rem;
  color: var(--color-danger);
  font-size: 1.1rem;
}

.session-error-state strong,
.chat-error-state strong {
  display: block;
  margin-bottom: var(--space-1);
}

.session-error-state p,
.chat-error-state p {
  margin: 0 0 var(--space-3);
  color: var(--color-text-secondary);
}

.back-to-latest {
  position: absolute;
  right: 50%;
  bottom: var(--space-4);
  z-index: 2;
  margin: 0;
  box-shadow: var(--shadow-popover);
  transform: translateX(50%);
}

.input-area {
  position: relative;
  z-index: 1;
  flex: 0 0 auto;
  padding: var(--space-4) var(--page-padding) var(--space-3);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface-elevated);
  box-shadow: 0 -12px 32px var(--color-backdrop);
}

.input-shell {
  display: flex;
  align-items: flex-end;
  gap: var(--space-3);
  width: min(100%, var(--chat-max-width));
  margin: 0 auto;
  padding: var(--space-2);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-panel);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.input-field {
  flex: 1;
}

.input-field :deep(.el-textarea__inner) {
  min-height: 2.5rem;
  padding: var(--space-2) var(--space-3);
  background: transparent;
  box-shadow: none;
  resize: none;
}

.input-field :deep(.el-textarea__inner:hover),
.input-field :deep(.el-textarea__inner:focus) {
  background: var(--color-surface-subtle);
  box-shadow: 0 0 0 1px var(--color-primary) inset, var(--focus-ring);
}

.send-button {
  min-width: 5.25rem;
}

.input-helper {
  width: min(100%, var(--chat-max-width));
  margin: var(--space-2) auto 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}

.message-enter-active,
.message-leave-active {
  transition:
    opacity 180ms var(--ease-standard),
    transform 180ms var(--ease-standard);
}

.message-enter-from {
  opacity: 0;
  transform: translateY(var(--space-2));
}

.message-leave-to {
  opacity: 0;
  transform: translateY(calc(var(--space-1) * -1));
}

.message-move {
  transition: transform 180ms var(--ease-standard);
}

.jump-latest-enter-active,
.jump-latest-leave-active {
  transition:
    opacity var(--duration-control) var(--ease-standard),
    transform var(--duration-control) var(--ease-standard);
}

.jump-latest-enter-from,
.jump-latest-leave-to {
  opacity: 0;
  transform: translate(50%, var(--space-2));
}

@keyframes skeleton-shimmer {
  from {
    background-position: 100% 0;
  }

  to {
    background-position: -100% 0;
  }
}

@media (max-width: 767px) {
  .message-list {
    padding-top: var(--space-5);
  }

  .message-stack {
    gap: var(--space-5);
  }

  .input-area {
    padding-top: var(--space-3);
  }

  .input-shell {
    gap: var(--space-2);
  }

  .send-button {
    min-width: 2.75rem;
    padding: 0 var(--space-3);
  }

  .send-button span {
    display: none;
  }
}
</style>
