import { effectScope } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  STREAM_BATCH_INTERVAL,
  STREAM_MARKDOWN_INTERVAL,
  useStreamingBuffer
} from './useStreamingBuffer'

describe('useStreamingBuffer', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T00:00:00.000Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('commits tokens in 40ms batches and throttles Markdown to 120ms', () => {
    const render = vi.fn((text) => `<p>${text}</p>`)
    const scope = effectScope()
    const buffer = scope.run(() => useStreamingBuffer({ render }))

    buffer.append('你')
    buffer.append('好')

    vi.advanceTimersByTime(STREAM_BATCH_INTERVAL - 1)
    expect(buffer.text.value).toBe('')

    vi.advanceTimersByTime(1)
    expect(buffer.text.value).toBe('你好')
    expect(buffer.rendered.value).toBe('')
    expect(render).not.toHaveBeenCalled()

    buffer.append('！')
    vi.advanceTimersByTime(STREAM_BATCH_INTERVAL)
    expect(buffer.text.value).toBe('你好！')

    vi.advanceTimersByTime(STREAM_MARKDOWN_INTERVAL - (STREAM_BATCH_INTERVAL * 2))
    expect(render).toHaveBeenCalledTimes(1)
    expect(buffer.rendered.value).toBe('<p>你好！</p>')

    scope.stop()
  })

  it('flushes the pending batch and Markdown immediately on completion', () => {
    const render = vi.fn((text) => `<p>${text}</p>`)
    const scope = effectScope()
    const buffer = scope.run(() => useStreamingBuffer({ render }))

    buffer.append('final')
    expect(buffer.flush()).toBe('final')
    expect(buffer.text.value).toBe('final')
    expect(buffer.rendered.value).toBe('<p>final</p>')
    expect(render).toHaveBeenCalledTimes(1)

    vi.runAllTimers()
    expect(render).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('keeps interrupted content visible until a retry commits replacement text', () => {
    const render = vi.fn((text) => `<p>${text}</p>`)
    const scope = effectScope()
    const buffer = scope.run(() => useStreamingBuffer({ render }))

    buffer.reset('部分回复')
    buffer.beginReplacement()
    buffer.append('重新生成')

    vi.advanceTimersByTime(STREAM_BATCH_INTERVAL - 1)
    expect(buffer.text.value).toBe('部分回复')
    expect(buffer.rendered.value).toBe('<p>部分回复</p>')

    vi.advanceTimersByTime(1)
    expect(buffer.text.value).toBe('重新生成')
    expect(buffer.rendered.value).toBe('<p>部分回复</p>')

    buffer.flush()
    expect(buffer.rendered.value).toBe('<p>重新生成</p>')
    scope.stop()
  })
})
