<template>
  <section class="chat-container" aria-label="AI 求职顾问对话">
    <div
      ref="msgListRef"
      class="message-list"
      role="log"
      aria-live="polite"
      aria-relevant="additions text"
    >
      <div v-if="!messages.length && !streaming" class="chat-empty-state">
        <div class="empty-icon" aria-hidden="true">
          <el-icon><ChatDotRound /></el-icon>
        </div>
        <p class="technical-label">CAREER INTELLIGENCE</p>
        <h2>{{ emptyStateTitle }}</h2>
        <p>{{ emptyStateDescription }}</p>
      </div>

      <div
        v-for="(msg, index) in messages"
        :key="msg.id || `${msg.role}-${msg.timestamp || index}-${index}`"
        :class="['msg-row', msg.role === 'user' ? 'msg-row--user' : 'msg-row--assistant']"
      >
        <div v-if="msg.role === 'assistant'" class="assistant-avatar" aria-hidden="true">
          <el-icon><Cpu /></el-icon>
        </div>

        <div class="msg-body">
          <article
            :class="['message-surface', msg.role === 'user' ? 'message-surface--user' : 'message-surface--assistant']"
          >
            <p v-if="msg.role === 'assistant'" class="assistant-label">
              <el-icon aria-hidden="true"><Cpu /></el-icon>
              职达 AI
            </p>
            <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
          </article>

          <div :class="['msg-meta', msg.role === 'user' ? 'msg-meta--right' : 'msg-meta--left']">
            <time v-if="formatTimestamp(msg.timestamp)" :datetime="msg.timestamp">
              {{ formatTimestamp(msg.timestamp) }}
            </time>

            <template v-if="msg.role === 'assistant' && msg.sources?.length">
              <span class="meta-divider" aria-hidden="true"></span>
              <span class="source-heading">参考资料</span>
              <template v-for="source in msg.sources" :key="source.id || source.source">
                <a
                  v-if="isWebUrl(source.source)"
                  :href="source.source"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="source-link"
                  :aria-label="`打开参考资料：${source.title || source.source}`"
                >
                  <el-tag class="source-chip" effect="plain" size="small">
                    <el-icon aria-hidden="true"><Link /></el-icon>
                    {{ source.title || source.source }}
                  </el-tag>
                </a>
                <el-tag v-else class="source-chip" effect="plain" size="small">
                  <el-icon aria-hidden="true"><Document /></el-icon>
                  {{ source.title || source.source }}
                </el-tag>
              </template>
            </template>

            <template v-if="msg.role === 'assistant' && msg.id">
              <span class="meta-divider" aria-hidden="true"></span>
              <el-button
                class="feedback-button"
                :class="{ 'feedback-button--active': currentFeedback(msg) === 'like' }"
                text
                circle
                size="small"
                :aria-label="currentFeedback(msg) === 'like' ? '已标记为有帮助' : '标记为有帮助'"
                :title="currentFeedback(msg) === 'like' ? '已标记为有帮助' : '标记为有帮助'"
                @click="feedback(msg.id, 'like')"
              >
                <el-icon><CircleCheckFilled /></el-icon>
              </el-button>
              <el-button
                class="feedback-button feedback-button--negative"
                :class="{ 'feedback-button--active': currentFeedback(msg) === 'dislike' }"
                text
                circle
                size="small"
                :aria-label="currentFeedback(msg) === 'dislike' ? '已标记为需要改进' : '标记为需要改进'"
                :title="currentFeedback(msg) === 'dislike' ? '已标记为需要改进' : '标记为需要改进'"
                @click="feedback(msg.id, 'dislike')"
              >
                <el-icon><CircleCloseFilled /></el-icon>
              </el-button>
            </template>
          </div>
        </div>
      </div>

      <div v-if="streaming" class="msg-row msg-row--assistant msg-row--streaming">
        <div class="assistant-avatar" aria-hidden="true">
          <el-icon><Cpu /></el-icon>
        </div>
        <div class="msg-body">
          <article class="message-surface message-surface--assistant message-surface--streaming">
            <p class="assistant-label">
              <el-icon aria-hidden="true"><Cpu /></el-icon>
              职达 AI
            </p>
            <div v-if="streamingText" class="message-content" v-html="renderMarkdown(streamingText)"></div>
            <div v-else class="streaming-placeholder">
              <el-icon class="is-loading" aria-hidden="true"><Loading /></el-icon>
              正在整理回复
            </div>
          </article>
          <p class="streaming-status" role="status">
            <span class="streaming-pulse" aria-hidden="true"></span>
            正在生成回复
          </p>
        </div>
      </div>

      <div v-if="connectionError" class="chat-error-state" role="alert">
        <el-icon class="error-icon" aria-hidden="true"><WarningFilled /></el-icon>
        <div>
          <strong>回复未完成</strong>
          <p>{{ connectionError }}</p>
          <el-button v-if="lastRequest" size="small" plain @click="retryLastMessage">
            重新尝试
          </el-button>
        </div>
      </div>
    </div>

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
          :disabled="streaming"
          @keydown.enter.exact.prevent="send"
        />
        <el-button
          class="send-button"
          native-type="submit"
          type="primary"
          :disabled="!input.trim() || streaming"
          :loading="streaming"
          aria-label="发送消息"
        >
          <el-icon v-if="!streaming"><ArrowUp /></el-icon>
          <span>发送</span>
        </el-button>
      </div>
      <p class="input-helper">
        <span v-if="streaming">AI 正在生成回复，请稍候。</span>
        <span v-else>按 Enter 发送，Shift + Enter 换行。</span>
      </p>
    </form>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import {
  ArrowUp,
  ChatDotRound,
  CircleCheckFilled,
  CircleCloseFilled,
  Cpu,
  Document,
  Link,
  Loading,
  WarningFilled
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { submitFeedback } from '../api'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  sessionId: Number,
  userId: Number,
  quickText: { type: String, default: '' }
})
const emit = defineEmits(['send-message', 'kb-updated'])

const input = ref('')
const msgListRef = ref(null)
const streamingText = ref('')
const streaming = ref(false)
const connectionError = ref('')
const lastRequest = ref('')
const localFeedback = ref({})

const emptyStateTitle = computed(() => (
  props.sessionId ? '开始你的职业对话' : '选择一个会话后开始对话'
))
const emptyStateDescription = computed(() => (
  props.sessionId
    ? '可以分析简历、比对岗位要求，或准备下一场面试。'
    : '从左侧新建或选择会话，职达 AI 会在这里保留完整上下文。'
))

const isWebUrl = (value) => value && /^(https?:\/\/)/i.test(value)

const send = () => {
  const text = input.value.trim()
  if (!text || streaming.value) return

  if (!props.sessionId || !props.userId) {
    connectionError.value = '请先登录并选择一个会话后再发送消息。'
    ElMessage.warning('请先登录并选择会话')
    return
  }

  input.value = ''
  requestReply(text, true)
}

const retryLastMessage = () => {
  if (!lastRequest.value || streaming.value) return
  if (!props.sessionId || !props.userId) {
    connectionError.value = '当前会话不可用，请重新选择会话后再尝试。'
    return
  }
  requestReply(lastRequest.value, false)
}

const requestReply = async (text, shouldEmitUser) => {
  connectionError.value = ''
  lastRequest.value = text

  if (shouldEmitUser) {
    emit('send-message', [{
      role: 'user',
      content: text,
      timestamp: new Date().toISOString()
    }])
  }

  streaming.value = true
  streamingText.value = ''
  scrollToBottom()

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

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue

        try {
          const data = JSON.parse(line.slice(6))
          if (data.token) {
            streamingText.value += data.token
            scrollToBottom()
          } else if (data.done) {
            finalData = data
          } else if (data.error) {
            throw new Error(data.error)
          }
        } catch (error) {
          if (error instanceof SyntaxError) continue
          throw error
        }
      }
    }

    if (!finalData?.done) {
      throw new Error('连接已中断，未收到完整回复。')
    }

    const aiMessage = {
      role: 'assistant',
      content: streamingText.value,
      id: finalData.msg_id || null,
      sources: finalData.sources || [],
      timestamp: new Date().toISOString()
    }
    emit('send-message', [aiMessage])
    if (aiMessage.sources.length) emit('kb-updated')
    lastRequest.value = ''
  } catch (error) {
    connectionError.value = error instanceof Error
      ? error.message
      : '连接失败，请稍后重试。'
  } finally {
    streaming.value = false
    streamingText.value = ''
    scrollToBottom()
  }
}

const cleanSourceMarkers = (text) => {
  if (!text) return ''
  return text.replace(/【来源\d+[^】]*】/g, '')
}

const renderMarkdown = (text) => {
  if (!text) return ''
  return DOMPurify.sanitize(marked(cleanSourceMarkers(text)))
}

const formatTimestamp = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (msgListRef.value) {
      msgListRef.value.scrollTop = msgListRef.value.scrollHeight
    }
  })
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

watch(() => props.quickText, (text) => {
  if (text) {
    input.value = text.trim()
    nextTick(send)
  }
})

watch(() => props.messages, scrollToBottom, { deep: true, flush: 'post' })
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: var(--color-canvas);
}

.message-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-6);
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-8) var(--page-padding) var(--space-4);
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

.msg-row {
  display: flex;
  gap: var(--space-3);
  width: min(100%, var(--chat-max-width));
}

.msg-row--assistant {
  align-self: flex-start;
}

.msg-row--user {
  align-self: flex-end;
  width: min(76%, 38rem);
}

.assistant-avatar {
  display: grid;
  width: 2rem;
  height: 2rem;
  flex: 0 0 auto;
  margin-top: var(--space-1);
  place-items: center;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-control);
  background: var(--color-surface-elevated);
  box-shadow: var(--shadow-popover);
  color: var(--color-cyan);
  font-size: 1rem;
}

.msg-body {
  min-width: 0;
  flex: 1;
}

.message-surface {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  color: var(--color-text-primary);
}

.message-surface--assistant {
  padding: var(--space-5);
  background: var(--color-surface);
  border-top-left-radius: var(--radius-control);
  box-shadow: var(--shadow-card);
}

.message-surface--user {
  padding: var(--space-4) var(--space-5);
  border-color: var(--color-primary);
  border-top-right-radius: var(--radius-control);
  background: var(--color-primary);
  color: var(--color-on-primary);
}

.assistant-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 0 var(--space-3);
  color: var(--color-cyan);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  font-weight: 600;
  letter-spacing: .04em;
}

.message-content {
  max-width: 70ch;
  overflow-wrap: anywhere;
  font-size: var(--font-size-body);
  line-height: 1.8;
}

.message-surface--user .message-content {
  margin-left: auto;
}

.message-content :deep(h1),
.message-content :deep(h2),
.message-content :deep(h3),
.message-content :deep(h4) {
  margin: var(--space-5) 0 var(--space-2);
  color: inherit;
  font-size: var(--font-size-component-title);
  line-height: var(--line-height-component-title);
}

.message-content :deep(h1:first-child),
.message-content :deep(h2:first-child),
.message-content :deep(h3:first-child),
.message-content :deep(h4:first-child),
.message-content :deep(p:first-child) {
  margin-top: 0;
}

.message-content :deep(p),
.message-content :deep(ul),
.message-content :deep(ol),
.message-content :deep(blockquote) {
  margin: 0 0 var(--space-3);
}

.message-content :deep(ul),
.message-content :deep(ol) {
  padding-left: var(--space-5);
}

.message-content :deep(li + li) {
  margin-top: var(--space-1);
}

.message-content :deep(blockquote) {
  padding-left: var(--space-4);
  border-left: 2px solid var(--color-cyan);
  color: var(--color-text-secondary);
}

.message-content :deep(code) {
  padding: .12em .36em;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: .9em;
}

.message-surface--user .message-content :deep(code) {
  border-color: var(--color-primary-hover);
  background: var(--color-primary-pressed);
  color: var(--color-on-primary);
}

.message-content :deep(pre) {
  margin: var(--space-4) 0;
  padding: var(--space-4);
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
}

.message-content :deep(pre code) {
  padding: 0;
  border: 0;
  background: transparent;
}

.message-surface--user .message-content :deep(a) {
  color: var(--color-on-primary);
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 1.5rem;
  margin-top: var(--space-2);
  padding: 0 var(--space-2);
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.msg-meta--right {
  justify-content: flex-end;
}

.msg-meta--left {
  flex-wrap: wrap;
}

.meta-divider {
  width: .18rem;
  height: .18rem;
  border-radius: var(--radius-pill);
  background: var(--color-border-strong);
}

.source-heading {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: .68rem;
  letter-spacing: .04em;
}

.source-link {
  color: inherit;
  text-decoration: none;
}

.source-chip {
  --el-tag-bg-color: var(--color-surface-subtle);
  --el-tag-border-color: var(--color-border);
  --el-tag-text-color: var(--color-text-secondary);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  max-width: 16rem;
}

.source-chip :deep(.el-tag__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feedback-button {
  --el-button-text-color: var(--color-text-muted);
  --el-button-hover-text-color: var(--color-success);
  --el-button-hover-bg-color: var(--color-success-soft);
  width: 1.5rem;
  min-height: 1.5rem;
  padding: 0;
}

.feedback-button--negative {
  --el-button-hover-text-color: var(--color-danger);
  --el-button-hover-bg-color: var(--color-danger-soft);
}

.feedback-button--active {
  --el-button-text-color: var(--color-success);
  --el-button-bg-color: var(--color-success-soft);
}

.feedback-button--negative.feedback-button--active {
  --el-button-text-color: var(--color-danger);
  --el-button-bg-color: var(--color-danger-soft);
}

.message-surface--streaming {
  min-width: min(34rem, 100%);
}

.streaming-placeholder,
.streaming-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}

.streaming-placeholder {
  min-height: 2rem;
}

.streaming-status {
  margin: var(--space-2) 0 0;
  padding: 0 var(--space-2);
}

.streaming-pulse {
  width: .45rem;
  height: .45rem;
  border-radius: var(--radius-pill);
  background: var(--color-cyan);
  box-shadow: 0 0 0 .18rem var(--color-info-soft);
  animation: streaming-pulse 1.5s var(--ease-standard) infinite;
}

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

.error-icon {
  margin-top: .1rem;
  color: var(--color-danger);
  font-size: 1.1rem;
}

.chat-error-state strong {
  display: block;
  margin-bottom: var(--space-1);
}

.chat-error-state p {
  margin: 0 0 var(--space-3);
  color: var(--color-text-secondary);
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

@keyframes streaming-pulse {
  0%,
  100% {
    opacity: .55;
    transform: scale(.82);
  }

  50% {
    opacity: 1;
    transform: scale(1);
  }
}

@media (max-width: 767px) {
  .message-list {
    gap: var(--space-5);
    padding-top: var(--space-5);
  }

  .msg-row--user {
    width: min(88%, 38rem);
  }

  .message-surface--assistant {
    padding: var(--space-4);
  }

  .assistant-avatar {
    width: 1.75rem;
    height: 1.75rem;
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
