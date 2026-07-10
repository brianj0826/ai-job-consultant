<template>
  <div class="chat-container">
    <!-- 消息列表 -->
    <div class="message-list" ref="msgListRef">
      <div
        v-for="(msg, i) in messages"
        :key="i"
        :class="['msg-row', msg.role === 'user' ? 'msg-row--user' : 'msg-row--bot']"
        class="msg-enter"
      >
        <!-- AI 头像 -->
        <div v-if="msg.role === 'assistant'" class="avatar avatar-bot">🤖</div>

        <div class="msg-body">
          <!-- 气泡 -->
          <div
            :class="['bubble', msg.role === 'user' ? 'bubble--user' : 'bubble--bot']"
            v-html="renderMarkdown(msg.content)"
          ></div>

          <!-- 时间 + 来源 + 反馈 -->
          <div :class="['msg-meta', msg.role === 'user' ? 'msg-meta--right' : 'msg-meta--left']">
            <template v-if="msg.role === 'assistant' && msg.sources && msg.sources.length">
              <span class="meta-sep">·</span>
              <span class="source-label">📖 参考</span>
              <template v-for="s in msg.sources" :key="s.id">
                <a
                  v-if="isWebUrl(s.source)"
                  :href="s.source"
                  target="_blank"
                  class="source-link"
                >
                  <el-tag size="small" type="warning" effect="plain" round>
                    🌐 {{ s.title || s.source }}
                  </el-tag>
                </a>
                <el-tag v-else size="small" type="info" effect="plain" round>
                  📄 {{ s.title || s.source }}
                </el-tag>
              </template>
            </template>

            <template v-if="msg.role === 'assistant' && msg.id">
              <span class="meta-sep">·</span>
              <button
                class="fb-btn"
                :class="{ 'fb-btn--active': msg.feedback === 'like' }"
                @click="feedback(msg.id, 'like')"
                title="赞"
              >👍</button>
              <button
                class="fb-btn"
                :class="{ 'fb-btn--active': msg.feedback === 'dislike' }"
                @click="feedback(msg.id, 'dislike')"
                title="踩"
              >👎</button>
            </template>
          </div>
        </div>

      </div>

      <!-- 流式输出 -->
      <div v-if="streaming" class="msg-row msg-row--bot msg-enter">
        <div class="avatar avatar-bot">🤖</div>
        <div class="msg-body">
          <div class="bubble bubble--bot streaming-bubble" v-html="renderMarkdown(streamingText)"></div>
          <div class="msg-meta msg-meta--left">
            <span class="typing-indicator">● 正在输入...</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <el-input
        v-model="input"
        placeholder="请输入问题..."
        @keyup.enter="send"
        size="large"
        class="input-field"
      >
        <template #append>
          <el-button @click="send" type="primary" :disabled="streaming">发送</el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { submitFeedback } from '../api'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'

const props = defineProps({
  messages: Array,
  sessionId: Number,
  userId: Number,
  quickText: { type: String, default: '' }
})
const emit = defineEmits(['send-message', 'kb-updated'])

const isWebUrl = (str) => str && (str.startsWith('http://') || str.startsWith('https://'))

const input = ref('')
const msgListRef = ref(null)
const streamingText = ref('')
const streaming = ref(false)

const send = async () => {
  const text = input.value.trim()
  if (!text || !props.sessionId || !props.userId) {
    ElMessage.warning('请先登录并选择会话')
    return
  }

  const userMsg = { role: 'user', content: text, timestamp: new Date().toISOString() }
  input.value = ''

  emit('send-message', [userMsg])

  streaming.value = true
  streamingText.value = ''
  scrollToBottom()

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, user_id: props.userId, session_id: props.sessionId })
    })

    if (!response.ok) {
      const err = await response.json()
      ElMessage.error(err.detail || '请求失败')
      streaming.value = false
      return
    }

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
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.token) {
              streamingText.value += data.token
              scrollToBottom()
            } else if (data.done) {
              finalData = data
            } else if (data.error) {
              ElMessage.error(data.error)
            }
          } catch (e) { /* skip */ }
        }
      }
    }

    const aiMsg = {
      role: 'assistant',
      content: streamingText.value,
      id: finalData?.msg_id || null,
      sources: finalData?.sources || [],
      timestamp: new Date().toISOString()
    }
    emit('send-message', [aiMsg])
    if (aiMsg.sources.length) emit('kb-updated')
  } catch (e) {
    ElMessage.error('连接失败，请稍后重试')
  } finally {
    streaming.value = false
    streamingText.value = ''
  }
  scrollToBottom()
}

// 过滤掉 RAG 引用标记（来源信息已在下方标签展示）
const cleanSourceMarkers = (text) => {
  if (!text) return ''
  // 去掉 【来源1】、【来源2: xxx】等标记
  return text.replace(/【来源\d+[^】]*】/g, '')
}

const renderMarkdown = (text) => {
  if (!text) return ''
  return marked(cleanSourceMarkers(text))
}

const scrollToBottom = () => {
  nextTick(() => {
    if (msgListRef.value) {
      msgListRef.value.scrollTop = msgListRef.value.scrollHeight
    }
  })
}

const feedback = async (msgId, type) => {
  try {
    await submitFeedback(msgId, type)
    ElMessage.success('感谢反馈！')
  } catch (e) {
    ElMessage.error('反馈提交失败')
  }
}

// 快捷消息自动填充
watch(() => props.quickText, (text) => {
  if (text) {
    input.value = text.trim()
    nextTick(() => send())
  }
})

watch(() => props.messages, () => scrollToBottom(), { deep: true, flush: 'post' })
</script>

<style scoped>
/* ============ 容器 ============ */
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: linear-gradient(180deg, #f5f6fa 0%, #edf0f5 100%);
}
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 24px 8px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.message-list::-webkit-scrollbar { width: 6px; }
.message-list::-webkit-scrollbar-thumb { background: #d0d5e0; border-radius: 3px; }
.message-list::-webkit-scrollbar-track { background: transparent; }

/* ============ 消息行 ============ */
.msg-row {
  display: flex;
  gap: 12px;
  margin-bottom: 22px;
  max-width: 80%;
}
.msg-row--bot { align-self: flex-start; }
.msg-row--user { align-self: flex-end; }

/* ============ 头像 ============ */
.avatar {
  width: 38px; height: 38px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; flex-shrink: 0; margin-top: 4px;
}
.avatar-bot {
  background: linear-gradient(135deg, #5b7fff 0%, #6c5ce7 100%);
  box-shadow: 0 2px 8px rgba(91,127,255,0.25);
}
.msg-body { display: flex; flex-direction: column; }

/* ============ 气泡 ============ */
.bubble {
  padding: 14px 18px; border-radius: 18px;
  line-height: 1.75; font-size: 14px; word-break: break-word;
}
/* AI 气泡：白底 + 左侧蓝线 */
.bubble--bot {
  background: #fff; color: #303133;
  border-top-left-radius: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.06);
  border-left: 3px solid #5b7fff;
  padding-left: 15px;
}
/* 用户气泡：蓝紫渐变 */
.bubble--user {
  background: linear-gradient(135deg, #5b7fff 0%, #6c5ce7 100%);
  color: #fff; border-top-right-radius: 6px;
  box-shadow: 0 4px 14px rgba(91,127,255,0.28);
}
.bubble :deep(h1), .bubble :deep(h2), .bubble :deep(h3) { margin: 0.3em 0; }
.bubble :deep(p) { margin: 0.3em 0; }
.bubble :deep(strong) { font-weight: 700; }
.bubble :deep(code) { background: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.bubble--user :deep(code) { background: rgba(255,255,255,0.2); color: #fff; }

/* ============ 消息元信息 ============ */
.msg-meta { display: flex; align-items: center; gap: 4px; margin-top: 6px; padding: 0 6px; flex-wrap: wrap; }
.msg-meta--left { justify-content: flex-start; }
.msg-meta--right { justify-content: flex-end; }
.source-label { font-size: 11px; color: #909399; }
.source-link { text-decoration: none; }
.source-link:hover { opacity: 0.8; }
.fb-btn {
  border: none; background: transparent; cursor: pointer;
  font-size: 13px; padding: 0 2px; opacity: 0.4;
  transition: all 0.2s;
}
.fb-btn:hover, .fb-btn--active { opacity: 1; transform: scale(1.15); }

/* ============ 流式 ============ */
.streaming-bubble { opacity: 0.88; }
.typing-indicator { font-size: 11px; color: #909399; animation: blink 1.4s ease-in-out infinite; }
@keyframes blink { 0%,100%{opacity:1;} 50%{opacity:0.3;} }

/* ============ 消息动画 ============ */
.msg-enter { animation: msgFadeIn 0.3s ease-out; }
@keyframes msgFadeIn { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }

/* ============ 底部输入区 ============ */
.input-area {
  padding: 14px 24px;
  background: #fff;
  border-top: 1.5px solid #eef0f6;
  box-shadow: 0 -2px 12px rgba(0,0,0,0.03);
}
.input-field :deep(.el-input__wrapper) {
  border-radius: 14px;
  border: 1.5px solid #e8ecf2;
  background: #f9fafc;
  box-shadow: none;
  transition: all 0.25s ease;
  padding: 6px 12px;
}
.input-field :deep(.el-input__wrapper:hover) {
  border-color: #c8cee0;
  background: #fff;
}
.input-field :deep(.el-input__wrapper.is-focus) {
  border-color: #5b7fff;
  box-shadow: 0 0 0 3px rgba(91,127,255,0.08);
  background: #fff;
}
/* 发送按钮 */
.input-field :deep(.el-input-group__append) {
  background: linear-gradient(135deg, #5b7fff 0%, #6c5ce7 100%);
  border: none; border-radius: 0 14px 14px 0;
  box-shadow: 0 2px 8px rgba(91,127,255,0.3);
  transition: all 0.25s ease;
}
.input-field :deep(.el-input-group__append:hover) {
  box-shadow: 0 4px 14px rgba(91,127,255,0.4);
  opacity: 0.95;
}
.input-field :deep(.el-input-group__append .el-button) {
  color: #fff; font-weight: 600;
}
</style>
