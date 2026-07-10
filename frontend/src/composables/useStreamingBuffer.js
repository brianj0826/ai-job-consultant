import { getCurrentScope, onScopeDispose, readonly, ref } from 'vue'

export const STREAM_BATCH_INTERVAL = 40
export const STREAM_MARKDOWN_INTERVAL = 120

export const useStreamingBuffer = ({
  batchInterval = STREAM_BATCH_INTERVAL,
  markdownInterval = STREAM_MARKDOWN_INTERVAL,
  render = (value) => value
} = {}) => {
  const text = ref('')
  const rendered = ref('')

  let pending = ''
  let batchTimer = null
  let renderTimer = null
  let lastRenderAt = Date.now()
  let replaceOnCommit = false

  const clearBatchTimer = () => {
    if (batchTimer === null) return
    clearTimeout(batchTimer)
    batchTimer = null
  }

  const clearRenderTimer = () => {
    if (renderTimer === null) return
    clearTimeout(renderTimer)
    renderTimer = null
  }

  const renderNow = () => {
    clearRenderTimer()
    rendered.value = text.value ? render(text.value) : ''
    lastRenderAt = Date.now()
  }

  const scheduleRender = () => {
    if (renderTimer !== null) return
    const elapsed = Date.now() - lastRenderAt
    const delay = Math.max(0, markdownInterval - elapsed)
    renderTimer = setTimeout(() => {
      renderTimer = null
      renderNow()
    }, delay)
  }

  const commitPending = () => {
    clearBatchTimer()
    if (!pending) return false

    if (replaceOnCommit) {
      text.value = pending
      replaceOnCommit = false
    } else {
      text.value += pending
    }
    pending = ''
    return true
  }

  const commitBatch = () => {
    if (commitPending()) scheduleRender()
  }

  const append = (token) => {
    if (!token) return
    pending += token
    if (batchTimer === null) {
      batchTimer = setTimeout(commitBatch, batchInterval)
    }
  }

  const flush = () => {
    const changed = commitPending()
    if (changed || renderTimer !== null || rendered.value !== text.value) renderNow()
    return text.value
  }

  const reset = (initialText = '') => {
    clearBatchTimer()
    clearRenderTimer()
    pending = ''
    replaceOnCommit = false
    text.value = initialText
    rendered.value = initialText ? render(initialText) : ''
    lastRenderAt = Date.now()
  }

  // Keep an interrupted reply visible until the retry produces its first batch.
  const beginReplacement = () => {
    clearBatchTimer()
    clearRenderTimer()
    pending = ''
    replaceOnCommit = true
    lastRenderAt = Date.now()
  }

  const stop = () => {
    clearBatchTimer()
    clearRenderTimer()
    pending = ''
    replaceOnCommit = false
  }

  if (getCurrentScope()) onScopeDispose(stop)

  return {
    append,
    beginReplacement,
    flush,
    rendered: readonly(rendered),
    reset,
    stop,
    text: readonly(text)
  }
}
