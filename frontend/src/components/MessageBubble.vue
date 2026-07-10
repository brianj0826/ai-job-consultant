<template>
  <div
    :class="['msg-row', isUser ? 'msg-row--user' : 'msg-row--assistant', {
      'msg-row--streaming': streaming,
      'msg-row--interrupted': interrupted
    }]"
    :aria-busy="streaming ? 'true' : undefined"
  >
    <div v-if="!isUser" class="assistant-avatar" aria-hidden="true">
      <el-icon><Cpu /></el-icon>
    </div>

    <div class="msg-body">
      <article
        :class="[
          'message-surface',
          isUser ? 'message-surface--user' : 'message-surface--assistant',
          { 'message-surface--streaming': streaming || interrupted }
        ]"
      >
        <p v-if="!isUser" class="assistant-label">
          <el-icon aria-hidden="true"><Cpu /></el-icon>
          职达 AI
        </p>

        <div v-if="renderedContent" class="message-content" v-html="renderedContent"></div>
        <div v-else-if="streaming" class="streaming-placeholder">
          <el-icon class="is-loading" aria-hidden="true"><Loading /></el-icon>
          正在整理回复
        </div>

        <div v-if="interrupted" class="inline-interruption" role="alert">
          <el-icon class="inline-interruption__icon" aria-hidden="true"><WarningFilled /></el-icon>
          <div>
            <strong>回复生成中断</strong>
            <p>{{ error || '连接已中断，请重新尝试。' }}</p>
            <el-button size="small" plain :loading="streaming" @click="emit('retry')">
              <el-icon aria-hidden="true"><RefreshRight /></el-icon>
              重新尝试
            </el-button>
          </div>
        </div>
      </article>

      <p v-if="streaming" class="streaming-status" aria-hidden="true">
        <span class="streaming-pulse"></span>
        正在生成回复
      </p>

      <div v-if="!streaming && !interrupted" :class="['msg-meta', isUser ? 'msg-meta--right' : 'msg-meta--left']">
        <time v-if="formattedTimestamp" :datetime="message.timestamp">
          {{ formattedTimestamp }}
        </time>

        <template v-if="!isUser && message.sources?.length">
          <span class="meta-divider" aria-hidden="true"></span>
          <span class="source-heading">参考资料</span>
          <template v-for="source in message.sources" :key="source.id || source.source">
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

        <template v-if="!isUser && message.id">
          <span class="meta-divider" aria-hidden="true"></span>
          <el-button
            class="feedback-button"
            :class="{ 'feedback-button--active': feedbackValue === 'like' }"
            text
            circle
            size="small"
            :aria-label="feedbackValue === 'like' ? '已标记为有帮助' : '标记为有帮助'"
            :title="feedbackValue === 'like' ? '已标记为有帮助' : '标记为有帮助'"
            @click="emit('feedback', message.id, 'like')"
          >
            <el-icon><CircleCheckFilled /></el-icon>
          </el-button>
          <el-button
            class="feedback-button feedback-button--negative"
            :class="{ 'feedback-button--active': feedbackValue === 'dislike' }"
            text
            circle
            size="small"
            :aria-label="feedbackValue === 'dislike' ? '已标记为需要改进' : '标记为需要改进'"
            :title="feedbackValue === 'dislike' ? '已标记为需要改进' : '标记为需要改进'"
            @click="emit('feedback', message.id, 'dislike')"
          >
            <el-icon><CircleCloseFilled /></el-icon>
          </el-button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  CircleCheckFilled,
  CircleCloseFilled,
  Cpu,
  Document,
  Link,
  Loading,
  RefreshRight,
  WarningFilled
} from '@element-plus/icons-vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

const props = defineProps({
  message: { type: Object, required: true },
  streaming: { type: Boolean, default: false },
  interrupted: { type: Boolean, default: false },
  error: { type: String, default: '' },
  renderedHtml: { type: String, default: '' },
  feedbackValue: { type: String, default: null }
})

const emit = defineEmits(['feedback', 'retry'])

const isUser = computed(() => props.message.role === 'user')
const isWebUrl = (value) => value && /^(https?:\/\/)/i.test(value)

const cleanSourceMarkers = (text) => text?.replace(/【来源\d+[^】]*】/g, '') || ''

// Each completed bubble owns its cache, so streaming updates in a sibling never
// reparse historical Markdown.
let cachedSource = null
let cachedHtml = ''
const renderCompletedMarkdown = (text) => {
  const source = cleanSourceMarkers(text)
  if (source === cachedSource) return cachedHtml
  cachedSource = source
  cachedHtml = source ? DOMPurify.sanitize(marked(source)) : ''
  return cachedHtml
}

const renderedContent = computed(() => (
  props.streaming || props.interrupted
    ? props.renderedHtml
    : renderCompletedMarkdown(props.message.content)
))

const formattedTimestamp = computed(() => {
  if (!props.message.timestamp) return ''
  const date = new Date(props.message.timestamp)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
})
</script>

<style scoped>
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

.message-surface--streaming {
  min-width: min(34rem, 100%);
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

.inline-interruption {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding-top: var(--space-4);
  margin-top: var(--space-4);
  border-top: 1px solid var(--color-danger);
}

.inline-interruption__icon {
  flex: 0 0 auto;
  margin-top: .15rem;
  color: var(--color-danger);
  font-size: 1.05rem;
}

.inline-interruption strong {
  display: block;
  margin-bottom: var(--space-1);
}

.inline-interruption p {
  margin: 0 0 var(--space-3);
  color: var(--color-text-secondary);
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
}
</style>
