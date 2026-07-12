<template>
  <section class="chat-container" aria-label="AI 求职顾问对话" :aria-busy="ariaBusy ? 'true' : 'false'">
    <div class="chat-ambient" aria-hidden="true">
      <span class="chat-ambient__glow chat-ambient__glow--violet"></span>
      <span class="chat-ambient__glow chat-ambient__glow--cyan"></span>
    </div>

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
      <div class="input-area__inner">
        <div
          class="input-shell"
          :class="{
            'input-shell--active': input.trim(),
            'input-shell--busy': streaming || isSessionLoading
          }"
        >
          <label class="sr-only" for="chat-message-input">向职达 AI 提问</label>
          <el-input
            id="chat-message-input"
            v-model="input"
            class="input-field"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 6 }"
            placeholder="描述你的求职问题，或粘贴一段职位描述…"
            :disabled="composerDisabled"
            @keydown.enter.exact.prevent="send"
          />

          <div class="composer-actions">
            <div class="composer-tools" aria-label="对话工具">
              <el-button
                class="composer-tool"
                text
                circle
                native-type="button"
                aria-label="从知识库上传文档"
                title="从知识库上传文档"
                @click="emit('request-document-upload')"
              >
                <el-icon aria-hidden="true"><Paperclip /></el-icon>
              </el-button>
              <span class="composer-tools__label">添加知识资料</span>
            </div>

            <el-button
              class="send-button"
              native-type="submit"
              type="primary"
              :disabled="!input.trim() || composerDisabled"
              :loading="streaming"
              :aria-label="streaming ? '正在生成回复' : '发送消息'"
            >
              <el-icon v-if="!streaming"><ArrowUp /></el-icon>
              <span>{{ streaming ? '生成中' : '发送' }}</span>
            </el-button>
          </div>
        </div>

        <p class="input-helper">
          <span v-if="streaming">AI 正在生成回复，请稍候。</span>
          <span v-else-if="rateLimitSeconds">请求过于频繁，{{ rateLimitSeconds }} 秒后可重试。</span>
          <span v-else-if="isSessionLoading">正在载入当前会话。</span>
          <span v-else>Enter 发送 · Shift + Enter 换行</span>
        </p>
        <p class="sr-only" aria-live="polite" aria-atomic="true">{{ rateLimitAnnouncement }}</p>
      </div>
    </form>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowDown,
  ArrowUp,
  ChatDotRound,
  Paperclip,
  RefreshRight,
  WarningFilled
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { getErrorMessage, streamMessage, submitFeedback } from '../api'
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

const emit = defineEmits(['send-message', 'kb-updated', 'retry-session', 'request-document-upload'])

const input = ref('')
const msgListRef = ref(null)
const streaming = ref(false)
const interrupted = ref(false)
const connectionError = ref('')
const standaloneError = ref('')
const lastRequest = ref(null)
const localFeedback = ref({})
const activeStreamKey = ref('stream-0')
const finalAnnouncement = ref('')
const rateLimitAnnouncement = ref('')
const isNearBottom = ref(true)
const hydratingHistory = ref(true)
const showSessionSkeleton = ref(false)
const rateLimitSeconds = ref(0)

let streamSequence = 0
let scrollFrame = null
let scrollForce = false
let hydrationFrame = null
let skeletonTimer = null
let activeStreamController = null
let rateLimitTimer = null

const createClientRequestId = () => {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID()
  return `chat-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

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
const composerDisabled = computed(() => (
  streaming.value
  || rateLimitSeconds.value > 0
  || isSessionLoading.value
  || hasSessionError.value
  || !props.sessionId
  || !props.userId
))
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
  requestReply(text, true, false, createClientRequestId())
}

const startRateLimitCooldown = (seconds) => {
  if (rateLimitTimer !== null) clearInterval(rateLimitTimer)
  rateLimitSeconds.value = Math.max(1, Number.parseInt(seconds || 1, 10))
  rateLimitAnnouncement.value = `请求过于频繁，请在 ${rateLimitSeconds.value} 秒后重试。`
  rateLimitTimer = setInterval(() => {
    rateLimitSeconds.value = Math.max(0, rateLimitSeconds.value - 1)
    if (rateLimitSeconds.value === 0) {
      clearInterval(rateLimitTimer)
      rateLimitTimer = null
      rateLimitAnnouncement.value = '现在可以重新发送消息。'
    }
  }, 1000)
}

const retryLastMessage = () => {
  if (!lastRequest.value || composerDisabled.value) return
  if (!props.sessionId || !props.userId) {
    connectionError.value = '当前会话不可用，请重新选择会话后再尝试。'
    interrupted.value = true
    return
  }
  requestReply(lastRequest.value.text, false, true, lastRequest.value.clientRequestId)
}

const requestReply = async (text, shouldEmitUser, reuseBubble, clientRequestId) => {
  connectionError.value = ''
  standaloneError.value = ''
  finalAnnouncement.value = ''
  lastRequest.value = { text, clientRequestId }

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

  const controller = new AbortController()
  activeStreamController = controller
  try {
    const response = await streamMessage({
      message: text,
      session_id: props.sessionId,
      client_request_id: clientRequestId
    }, { signal: controller.signal })

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
    lastRequest.value = null
    interrupted.value = false
    streaming.value = false
    nextTick(() => {
      finalAnnouncement.value = '职达 AI 的回复已完成。'
      scheduleScrollToBottom()
    })
  } catch (error) {
    if (error?.cause?.name === 'AbortError' || error?.name === 'AbortError') return
    flushStream()
    if (error?.status === 429) startRateLimitCooldown(error.retryAfter)
    connectionError.value = getErrorMessage(error, '连接失败，请稍后重试。')
    interrupted.value = true
  } finally {
    if (activeStreamController === controller) activeStreamController = null
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
  activeStreamController?.abort()
  activeStreamController = null
  lastRequest.value = null
  interrupted.value = false
  resetStream()
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
  activeStreamController?.abort()
  cancelFrame(scrollFrame)
  cancelFrame(hydrationFrame)
  if (skeletonTimer !== null) clearTimeout(skeletonTimer)
  if (rateLimitTimer !== null) clearInterval(rateLimitTimer)
})
</script>

<style scoped>
.chat-container {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background:
    radial-gradient(circle at 76% 12%, var(--color-aurora-blue-soft), transparent 30rem),
    radial-gradient(circle at 22% 78%, var(--color-aurora-violet-soft), transparent 34rem),
    color-mix(in srgb, var(--color-canvas) 94%, transparent);
}

.chat-ambient {
  position: absolute;
  z-index: -1;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.chat-ambient::before {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, var(--color-orbit) 1px, transparent 1px),
    linear-gradient(to bottom, var(--color-orbit) 1px, transparent 1px);
  background-size: 5rem 5rem;
  content: '';
  opacity: .08;
  -webkit-mask-image: linear-gradient(to bottom, transparent, black 18%, transparent 78%);
  mask-image: linear-gradient(to bottom, transparent, black 18%, transparent 78%);
}

.chat-ambient__glow {
  position: absolute;
  width: 20rem;
  height: 20rem;
  border-radius: var(--radius-pill);
  filter: blur(80px);
  opacity: .28;
}

.chat-ambient__glow--violet {
  top: 26%;
  left: -12rem;
  background: var(--color-aurora-violet-soft);
}

.chat-ambient__glow--cyan {
  right: -13rem;
  bottom: 4%;
  background: var(--color-aurora-cyan-soft);
}

.conversation-region {
  position: relative;
  z-index: 1;
  flex: 1;
  min-height: 0;
}

.message-list {
  height: 100%;
  overflow-y: auto;
  padding: clamp(var(--space-8), 5vh, var(--space-16)) var(--page-padding) var(--space-6);
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.message-stack {
  display: flex;
  flex-direction: column;
  gap: clamp(var(--space-8), 5vh, var(--space-12));
  width: min(100%, 64rem);
  min-height: 100%;
  margin: 0 auto;
}

.chat-empty-state {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  align-self: center;
  width: min(100%, 38rem);
  max-width: 38rem;
  min-height: 100%;
  padding: var(--space-16) var(--space-6);
  color: var(--color-text-secondary);
  text-align: center;
}

.empty-icon {
  position: relative;
  display: grid;
  width: 4rem;
  height: 4rem;
  margin-bottom: var(--space-6);
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--color-primary) 52%, var(--color-border));
  border-radius: var(--radius-pill);
  background: var(--aurora-gradient-soft);
  box-shadow: var(--aurora-glow);
  color: var(--color-cyan);
  font-size: 1.6rem;
}

.empty-icon::after {
  position: absolute;
  inset: -.65rem;
  border: 1px solid var(--color-orbit-strong);
  border-radius: inherit;
  content: '';
  opacity: .45;
}

.chat-empty-state .technical-label {
  margin-bottom: var(--space-2);
}

.chat-empty-state h2 {
  margin: 0 0 var(--space-3);
  color: var(--color-text-primary);
  font-size: clamp(var(--font-size-section-title), 2vw, 1.75rem);
  line-height: 1.25;
  letter-spacing: -.025em;
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
  width: 100%;
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
  width: 2.5rem;
  height: 2.5rem;
  flex: 0 0 auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
}

.session-skeleton__bubble {
  display: grid;
  flex: 1;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4) var(--space-5);
  border-left: 2px solid var(--color-border-strong);
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
  width: 100%;
  padding: var(--space-5);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-panel);
  background: var(--color-danger-soft);
  color: var(--color-text-primary);
  box-shadow: var(--shadow-card);
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
  bottom: var(--space-3);
  z-index: 3;
  margin: 0;
  border-color: color-mix(in srgb, var(--color-primary) 48%, var(--color-border));
  background: var(--color-surface-glass);
  box-shadow: var(--shadow-popover), 0 0 24px var(--color-primary-soft);
  color: var(--color-primary);
  -webkit-backdrop-filter: blur(var(--glass-blur));
  backdrop-filter: blur(var(--glass-blur));
  transform: translateX(50%);
}

.input-area {
  position: relative;
  z-index: 2;
  flex: 0 0 auto;
  padding: var(--space-4) var(--page-padding) var(--space-5);
  background: linear-gradient(to bottom, transparent, var(--color-canvas) var(--space-5));
}

.input-area__inner {
  width: min(100%, 64rem);
  margin: 0 auto;
}

.input-shell {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-3);
  border: 1px solid color-mix(in srgb, var(--color-primary) 58%, var(--color-border-strong));
  border-radius: var(--radius-panel);
  background:
    linear-gradient(var(--color-surface-glass), var(--color-surface-glass)) padding-box,
    var(--aurora-gradient) border-box;
  box-shadow:
    var(--shadow-elevated),
    0 0 34px color-mix(in srgb, var(--color-primary-soft) 58%, transparent);
  -webkit-backdrop-filter: blur(var(--glass-blur));
  backdrop-filter: blur(var(--glass-blur));
  transition:
    border-color var(--duration-control) var(--ease-standard),
    box-shadow var(--duration-control) var(--ease-standard),
    transform var(--duration-control) var(--ease-standard);
}

.input-shell:hover {
  border-color: color-mix(in srgb, var(--color-cyan) 70%, var(--color-border-strong));
}

.input-shell:focus-within,
.input-shell--active {
  border-color: transparent;
  box-shadow:
    var(--shadow-elevated),
    0 0 0 1px var(--color-primary),
    0 0 34px color-mix(in srgb, var(--color-cyan) 24%, transparent);
}

.input-shell--busy {
  border-color: color-mix(in srgb, var(--color-primary) 38%, var(--color-border));
}

.input-field {
  width: 100%;
}

.input-field :deep(.el-textarea__inner) {
  min-height: 4.75rem !important;
  max-height: 11rem;
  padding: var(--space-3) var(--space-3) var(--space-2);
  border: 0;
  border-radius: var(--radius-card);
  background: transparent;
  color: var(--color-text-primary);
  font-size: var(--font-size-body-large);
  line-height: var(--line-height-body-large);
  box-shadow: none;
  resize: none;
}

.input-field :deep(.el-textarea__inner:hover),
.input-field :deep(.el-textarea__inner:focus) {
  background: transparent;
  box-shadow: none;
}

.input-field :deep(.el-textarea__inner::placeholder) {
  color: var(--color-text-muted);
}

.input-field :deep(.el-textarea__inner:disabled) {
  color: var(--color-text-disabled);
  -webkit-text-fill-color: var(--color-text-disabled);
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-height: 2.75rem;
  padding: var(--space-1) 0 0 var(--space-1);
}

.composer-tools {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  color: var(--color-text-muted);
}

.composer-tool {
  --el-button-text-color: var(--color-text-secondary);
  --el-button-hover-text-color: var(--color-cyan);
  --el-button-hover-bg-color: var(--color-info-soft);
  width: 2.75rem;
  min-width: 2.75rem;
  min-height: 2.75rem;
  margin: 0;
  font-size: 1.15rem;
}

.composer-tool:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.composer-tools__label {
  overflow: hidden;
  font-size: var(--font-size-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.send-button {
  --el-button-bg-color: var(--color-primary);
  --el-button-border-color: transparent;
  --el-button-hover-bg-color: var(--color-primary-hover);
  --el-button-hover-border-color: transparent;
  --el-button-active-bg-color: var(--color-primary-pressed);
  --el-button-disabled-text-color: var(--color-text-disabled);
  --el-button-disabled-bg-color: var(--color-surface-hover);
  --el-button-disabled-border-color: var(--color-border);
  min-width: 6.75rem;
  min-height: 2.75rem;
  margin: 0;
  border: 0;
  background: var(--aurora-gradient);
  box-shadow: 0 10px 28px color-mix(in srgb, var(--color-primary) 28%, transparent);
  font-weight: 650;
}

.send-button:not(.is-disabled):hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.send-button.is-disabled {
  background: var(--color-surface-hover);
  box-shadow: none;
}

.input-helper {
  min-height: var(--line-height-caption);
  margin: var(--space-2) 0 0;
  padding: 0 var(--space-3);
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  letter-spacing: .01em;
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
    padding: var(--space-5) var(--space-4) var(--space-4);
    scrollbar-gutter: auto;
  }

  .message-stack {
    gap: var(--space-8);
  }

  .input-area {
    padding: var(--space-3) var(--space-3) max(var(--space-3), env(safe-area-inset-bottom));
  }

  .input-shell {
    gap: var(--space-1);
    padding: var(--space-2);
    border-radius: var(--radius-card);
  }

  .input-field :deep(.el-textarea__inner) {
    min-height: 4.25rem !important;
    padding: var(--space-3);
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
  }

  .composer-actions {
    gap: var(--space-2);
    padding-left: 0;
  }

  .composer-tools__label {
    display: none;
  }

  .send-button {
    min-width: 5.5rem;
    padding: 0 var(--space-4);
  }

  .input-helper {
    padding: 0 var(--space-2);
    font-size: .6875rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .message-enter-active,
  .message-leave-active,
  .message-move,
  .jump-latest-enter-active,
  .jump-latest-leave-active,
  .input-shell,
  .send-button {
    transition-duration: .01ms;
  }

  .session-skeleton__avatar,
  .session-skeleton__bubble span {
    animation: none;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .back-to-latest,
  .input-shell {
    -webkit-backdrop-filter: none;
    backdrop-filter: none;
    background: var(--color-surface);
  }
}
</style>
