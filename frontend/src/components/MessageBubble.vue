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
      <header v-if="!isUser" class="assistant-heading">
        <p class="assistant-label">
          <el-icon aria-hidden="true"><Cpu /></el-icon>
          职达 AI
        </p>
        <time v-if="formattedTimestamp" :datetime="message.timestamp">
          {{ formattedTimestamp }}
        </time>
      </header>

      <article
        :class="[
          'message-surface',
          isUser ? 'message-surface--user' : 'message-surface--assistant',
          { 'message-surface--streaming': streaming || interrupted }
        ]"
      >
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

      <div
        v-if="!streaming && !interrupted && (
          (isUser && formattedTimestamp)
          || (!isUser && (message.sources?.length || message.id))
        )"
        :class="['msg-meta', isUser ? 'msg-meta--right' : 'msg-meta--left']"
      >
        <time v-if="isUser && formattedTimestamp" :datetime="message.timestamp">
          {{ formattedTimestamp }}
        </time>

        <template v-if="!isUser && message.sources?.length">
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
          <span v-if="message.sources?.length" class="meta-divider" aria-hidden="true"></span>
          <el-button
            class="feedback-button"
            :class="{ 'feedback-button--active': feedbackValue === 'like' }"
            text
            :aria-label="feedbackValue === 'like' ? '已标记为有帮助' : '标记为有帮助'"
            :title="feedbackValue === 'like' ? '已标记为有帮助' : '标记为有帮助'"
            @click="emit('feedback', message.id, 'like')"
          >
            <el-icon aria-hidden="true"><CircleCheckFilled /></el-icon>
            <span>有帮助</span>
          </el-button>
          <el-button
            class="feedback-button feedback-button--negative"
            :class="{ 'feedback-button--active': feedbackValue === 'dislike' }"
            text
            :aria-label="feedbackValue === 'dislike' ? '已标记为需要改进' : '标记为需要改进'"
            :title="feedbackValue === 'dislike' ? '已标记为需要改进' : '标记为需要改进'"
            @click="emit('feedback', message.id, 'dislike')"
          >
            <el-icon aria-hidden="true"><CircleCloseFilled /></el-icon>
            <span>需要改进</span>
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
import {
  renderAccessibleHtml,
  renderAccessibleMarkdown
} from '../utils/markdownAccessibility'

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
  cachedHtml = renderAccessibleMarkdown(source)
  return cachedHtml
}

const renderedContent = computed(() => (
  props.streaming || props.interrupted
    ? renderAccessibleHtml(props.renderedHtml)
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
  gap: var(--space-5);
  width: 100%;
  min-width: 0;
}

.msg-row--assistant {
  align-self: flex-start;
}

.msg-row--user {
  align-self: stretch;
  justify-content: flex-end;
}

.msg-row--user .msg-body {
  max-width: min(78%, 36rem);
  flex: 0 1 36rem;
}

.assistant-avatar {
  display: grid;
  width: 2.75rem;
  height: 2.75rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--color-orbit-strong);
  border-radius: var(--radius-pill);
  background: var(--aurora-gradient-soft);
  box-shadow: 0 0 0 .3rem var(--color-aurora-violet-soft), var(--shadow-popover);
  color: var(--color-cyan);
  font-size: 1.125rem;
}

.msg-body {
  position: relative;
  min-width: 0;
  flex: 1;
}

.assistant-heading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 2.75rem;
  margin-bottom: var(--space-1);
  color: var(--color-text-muted);
}

.assistant-heading time {
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  font-variant-numeric: tabular-nums;
}

.message-surface {
  min-width: 0;
  color: var(--color-text-primary);
}

.message-surface--assistant {
  position: relative;
  padding: var(--space-3) var(--space-5) var(--space-4) var(--space-8);
  background: transparent;
}

.message-surface--assistant::before {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 2px;
  border-radius: var(--radius-pill);
  background: var(--aurora-gradient);
  box-shadow: 0 0 1rem var(--color-primary-soft);
  content: '';
}

.message-surface--user {
  padding: var(--space-3) var(--space-5);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-card) var(--radius-card) var(--radius-control) var(--radius-card);
  background: linear-gradient(135deg, var(--color-surface-elevated), var(--color-primary-soft));
  box-shadow: var(--shadow-card);
  color: var(--color-text-primary);
}

.message-surface--streaming {
  min-height: 4.5rem;
}

.assistant-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0;
  color: var(--color-cyan);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.message-content {
  max-width: 74ch;
  overflow-wrap: anywhere;
  font-size: var(--font-size-body-large);
  line-height: 1.75;
}

.message-surface--user .message-content {
  margin-left: auto;
  font-size: var(--font-size-body);
  line-height: 1.65;
}

.message-content :deep(h1),
.message-content :deep(h2),
.message-content :deep(h3),
.message-content :deep(h4) {
  margin: var(--space-6) 0 var(--space-2);
  color: inherit;
  font-weight: 650;
  letter-spacing: -.015em;
}

.message-content :deep(h1) {
  font-size: 1.625rem;
  line-height: 1.3;
}

.message-content :deep(h2) {
  font-size: var(--font-size-section-title);
  line-height: var(--line-height-section-title);
}

.message-content :deep(h3),
.message-content :deep(h4) {
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
.message-content :deep(blockquote),
.message-content :deep(table),
.message-content :deep(pre) {
  margin: 0 0 var(--space-3);
}

.message-surface--assistant .message-content :deep(p),
.message-surface--assistant .message-content :deep(li) {
  color: var(--color-text-secondary);
}

.message-content :deep(strong) {
  color: var(--color-text-primary);
  font-weight: 650;
}

.message-content :deep(ul),
.message-content :deep(ol) {
  padding-left: var(--space-5);
}

.message-content :deep(li::marker) {
  color: var(--color-cyan);
}

.message-content :deep(li + li) {
  margin-top: var(--space-1);
}

.message-content :deep(blockquote) {
  padding-left: var(--space-4);
  border-left: 2px solid var(--color-cyan);
  color: var(--color-text-secondary);
}

.message-content :deep(a) {
  color: var(--color-electric-blue);
  font-weight: 600;
  text-decoration: underline;
  text-decoration-color: var(--color-border-strong);
  text-underline-offset: .2em;
}

.message-content :deep(a:hover) {
  color: var(--color-cyan);
  text-decoration-color: currentColor;
}

.message-content :deep(a:focus-visible) {
  border-radius: .2rem;
  outline: none;
  box-shadow: var(--focus-ring-strong);
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
  border-color: var(--color-border-strong);
  background: var(--color-surface-subtle);
  color: var(--color-text-primary);
}

.message-content :deep(pre) {
  max-width: 100%;
  padding: var(--space-4);
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-canvas-deep);
  box-shadow: inset 0 1px 0 var(--color-border);
}

.message-content :deep(pre code) {
  padding: 0;
  border: 0;
  background: transparent;
}

.message-content :deep(table) {
  display: block;
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  border-collapse: separate;
  border-spacing: 0;
  background: var(--color-surface-subtle);
  white-space: nowrap;
}

.message-content :deep(th),
.message-content :deep(td) {
  padding: var(--space-2) var(--space-3);
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  text-align: left;
}

.message-content :deep(th) {
  background: var(--color-primary-soft);
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
}

.message-content :deep(tr:last-child td) {
  border-bottom: 0;
}

.message-content :deep(th:last-child),
.message-content :deep(td:last-child) {
  border-right: 0;
}

.message-content :deep(hr) {
  height: 1px;
  margin: var(--space-5) 0;
  border: 0;
  background: var(--color-border);
}

.message-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-control);
}

.message-content :deep(:last-child) {
  margin-bottom: 0;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 2.75rem;
  margin-top: var(--space-1);
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
  padding-left: var(--space-8);
}

.meta-divider {
  width: 1px;
  height: 1.25rem;
  background: var(--color-border-strong);
}

.source-heading {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  font-weight: 600;
  letter-spacing: .06em;
}

.source-link {
  display: inline-flex;
  align-items: center;
  min-height: 2.75rem;
  border-radius: var(--radius-control);
  color: inherit;
  text-decoration: none;
}

.source-link:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.source-chip {
  --el-tag-bg-color: var(--color-surface-subtle);
  --el-tag-border-color: var(--color-border);
  --el-tag-text-color: var(--color-text-secondary);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  max-width: 16rem;
  min-height: 2.25rem;
  padding-inline: var(--space-3);
  border-radius: var(--radius-control);
}

.source-chip :deep(.el-tag__content) {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feedback-button {
  --el-button-text-color: var(--color-text-muted);
  --el-button-hover-text-color: var(--color-success-text);
  --el-button-hover-bg-color: var(--color-success-soft);
  min-width: auto;
  min-height: 2.75rem;
  margin: 0 !important;
  padding: 0 var(--space-3);
  border-radius: var(--radius-control);
}

.feedback-button--negative {
  --el-button-hover-text-color: var(--color-danger-text);
  --el-button-hover-bg-color: var(--color-danger-soft);
}

.feedback-button--active {
  --el-button-text-color: var(--color-success-text);
  --el-button-bg-color: var(--color-success-soft);
}

.feedback-button--negative.feedback-button--active {
  --el-button-text-color: var(--color-danger-text);
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
  min-height: 3rem;
}

.streaming-status {
  margin: var(--space-2) 0 0;
  padding: 0 var(--space-8);
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
  padding: var(--space-4);
  margin-top: var(--space-4);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-card);
  background: var(--color-danger-soft);
}

.inline-interruption__icon {
  flex: 0 0 auto;
  margin-top: .15rem;
  color: var(--color-danger-text);
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

.inline-interruption :deep(.el-button) {
  min-height: 2.75rem;
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
  .msg-row {
    gap: var(--space-3);
  }

  .msg-row--user .msg-body {
    max-width: 92%;
  }

  .message-surface--assistant {
    padding: var(--space-2) 0 var(--space-3) var(--space-5);
  }

  .assistant-avatar {
    width: 2.5rem;
    height: 2.5rem;
    box-shadow: 0 0 0 .2rem var(--color-aurora-violet-soft);
  }

  .assistant-heading {
    min-height: 2.5rem;
  }

  .message-content {
    font-size: var(--font-size-body);
    line-height: 1.7;
  }

  .message-content :deep(h1) {
    font-size: var(--font-size-section-title);
    line-height: var(--line-height-section-title);
  }

  .msg-meta--left,
  .streaming-status {
    padding-left: var(--space-5);
  }

  .msg-meta--left {
    align-items: flex-start;
  }

  .meta-divider {
    display: none;
  }

  .source-heading {
    width: 100%;
  }

  .source-link,
  .source-chip {
    max-width: 100%;
  }

  .feedback-button {
    flex: 1 1 auto;
  }

  .inline-interruption {
    padding: var(--space-3);
  }
}

@media (prefers-reduced-motion: reduce) {
  .streaming-pulse {
    animation: none;
    opacity: 1;
  }
}
</style>
