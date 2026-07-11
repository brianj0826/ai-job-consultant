import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getErrorMessage: vi.fn((error, fallback) => error?.message || fallback),
  streamMessage: vi.fn(),
  submitFeedback: vi.fn()
}))
const messageMocks = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  warning: vi.fn()
}))

vi.mock('../api', () => apiMocks)
vi.mock('element-plus', () => ({ ElMessage: messageMocks }))

import ChatWindow from './ChatWindow.vue'

const stubs = {
  ElButton: {
    props: {
      disabled: Boolean,
      loading: Boolean,
      nativeType: { type: String, default: 'button' }
    },
    emits: ['click'],
    template: `
      <button :type="nativeType" :disabled="disabled || loading" @click="$emit('click', $event)">
        <slot />
      </button>
    `
  },
  ElIcon: { template: '<span><slot /></span>' },
  ElInput: {
    inheritAttrs: false,
    props: {
      modelValue: { type: String, default: '' },
      disabled: Boolean
    },
    emits: ['update:modelValue', 'keydown'],
    template: `
      <textarea
        v-bind="$attrs"
        :value="modelValue"
        :disabled="disabled"
        @input="$emit('update:modelValue', $event.target.value)"
        @keydown="$emit('keydown', $event)"
      ></textarea>
    `
  },
  ElTag: { template: '<span><slot /></span>' }
}

const encoder = new TextEncoder()
const streamResponse = (steps) => {
  const read = vi.fn()
  steps.forEach((step) => {
    if (step instanceof Error) read.mockRejectedValueOnce(step)
    else read.mockResolvedValueOnce({ done: false, value: encoder.encode(step) })
  })
  read.mockResolvedValue({ done: true, value: undefined })
  return {
    ok: true,
    body: { getReader: () => ({ read }) }
  }
}

const mountChat = (props = {}) => mount(ChatWindow, {
  props: {
    messages: [],
    sessionId: 7,
    userId: 9,
    sessionStatus: 'ready',
    ...props
  },
  global: { stubs }
})

describe('ChatWindow', () => {
  let frameQueue

  const runFrame = () => {
    const callback = frameQueue.shift()
    if (callback) callback(16)
  }

  const drainFrames = () => {
    while (frameQueue.length) runFrame()
  }

  beforeEach(() => {
    vi.useFakeTimers()
    frameQueue = []
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback) => {
      frameQueue.push(callback)
      return frameQueue.length
    }))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    vi.stubGlobal('fetch', vi.fn())
    Object.values(messageMocks).forEach((mock) => mock.mockClear())
    apiMocks.submitFeedback.mockReset()
    apiMocks.streamMessage.mockReset()
    apiMocks.streamMessage.mockImplementation((data, options) => fetch('/api/chat/stream', {
      method: 'POST',
      body: JSON.stringify(data),
      signal: options?.signal
    }))
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('keeps the composer disabled until an authenticated session is selected', async () => {
    const wrapper = mountChat({ sessionId: null })
    expect(wrapper.get('textarea').attributes()).toHaveProperty('disabled')

    await wrapper.setProps({ sessionId: 7 })
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('delays the session skeleton, renders errors, and emits retry-session', async () => {
    const wrapper = mountChat({
      sessionStatus: 'loading',
      sessionError: ''
    })

    expect(wrapper.get('.message-list').attributes('aria-busy')).toBe('true')
    expect(wrapper.find('[data-testid="session-skeleton"]').exists()).toBe(false)
    expect(wrapper.find('.chat-empty-state').exists()).toBe(false)

    vi.advanceTimersByTime(149)
    await nextTick()
    expect(wrapper.find('[data-testid="session-skeleton"]').exists()).toBe(false)

    vi.advanceTimersByTime(1)
    await nextTick()
    expect(wrapper.find('[data-testid="session-skeleton"]').exists()).toBe(true)

    await wrapper.setProps({
      sessionStatus: 'error',
      sessionError: '服务暂时不可用'
    })
    expect(wrapper.get('[data-testid="session-error"]').text()).toContain('服务暂时不可用')

    await wrapper.get('[data-testid="session-error"] button').trigger('click')
    expect(wrapper.emitted('retry-session')).toEqual([[7]])
    wrapper.unmount()
  })

  it('retains interrupted output and retries in the same bubble without duplicating the user message', async () => {
    const wrapper = mountChat()
    await nextTick()
    drainFrames()

    fetch.mockResolvedValueOnce(streamResponse([
      'data: {"token":"部分回复"}\n',
      new Error('网络连接中断')
    ]))

    await wrapper.get('textarea').setValue('请分析我的简历')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    await nextTick()

    expect(wrapper.text()).toContain('部分回复')
    expect(wrapper.text()).toContain('网络连接中断')
    const interruptedBubble = wrapper.get('.msg-row--interrupted').element

    let resolveRetry
    fetch.mockImplementationOnce(() => new Promise((resolve) => {
      resolveRetry = resolve
    }))

    await wrapper.get('.inline-interruption button').trigger('click')
    await nextTick()
    expect(wrapper.get('.msg-row--streaming').element).toBe(interruptedBubble)
    expect(wrapper.text()).toContain('部分回复')

    resolveRetry(streamResponse([
      'data: {"token":"完整回复"}\n',
      'data: {"done":true,"msg_id":31,"sources":[]}\n'
    ]))
    await flushPromises()
    await nextTick()

    const emittedMessages = wrapper.emitted('send-message')
      .flatMap((event) => event[0])
    expect(emittedMessages.filter((message) => message.role === 'user')).toHaveLength(1)
    expect(emittedMessages.filter((message) => message.role === 'assistant')).toHaveLength(1)
    expect(emittedMessages.find((message) => message.role === 'assistant').content).toBe('完整回复')
    expect(wrapper.text()).toContain('职达 AI 的回复已完成。')
    expect(fetch).toHaveBeenCalledTimes(2)
    const requestBodies = fetch.mock.calls.map((call) => JSON.parse(call[1].body))
    expect(requestBodies[0]).not.toHaveProperty('user_id')
    expect(requestBodies[0].client_request_id).toBeTruthy()
    expect(requestBodies[1].client_request_id).toBe(requestBodies[0].client_request_id)
    wrapper.unmount()
  })

  it('honors Retry-After and blocks duplicate chat submissions during a 429 cooldown', async () => {
    const wrapper = mountChat()
    await nextTick()
    drainFrames()
    apiMocks.streamMessage.mockRejectedValueOnce(Object.assign(new Error('请求过于频繁'), {
      status: 429,
      retryAfter: 2
    }))

    await wrapper.get('textarea').setValue('请稍后重试')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('textarea').attributes()).toHaveProperty('disabled')
    expect(wrapper.text()).toContain('2 秒后可重试')
    await wrapper.get('form').trigger('submit')
    expect(apiMocks.streamMessage).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(1000)
    await nextTick()
    expect(wrapper.text()).toContain('1 秒后可重试')
    vi.advanceTimersByTime(1000)
    await nextTick()
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('uses an 80px follow threshold, offers return-to-latest, and schedules one scroll per frame', async () => {
    const firstMessage = {
      id: 1,
      role: 'assistant',
      content: '第一条',
      timestamp: '2026-01-01T00:00:00.000Z'
    }
    const wrapper = mountChat({ messages: [firstMessage] })
    await nextTick()
    drainFrames()
    frameQueue.length = 0

    const list = wrapper.get('.message-list')
    Object.defineProperty(list.element, 'scrollHeight', { configurable: true, value: 1000 })
    Object.defineProperty(list.element, 'clientHeight', { configurable: true, value: 400 })
    list.element.scrollTop = 500
    await list.trigger('scroll')

    expect(wrapper.find('.back-to-latest').exists()).toBe(true)
    await wrapper.get('.back-to-latest').trigger('click')
    expect(frameQueue).toHaveLength(1)
    runFrame()
    expect(list.element.scrollTop).toBe(1000)

    list.element.scrollTop = 520
    await list.trigger('scroll')
    frameQueue.length = 0

    await wrapper.setProps({
      messages: [firstMessage, { id: 2, role: 'assistant', content: '第二条' }]
    })
    await flushPromises()
    expect(frameQueue).toHaveLength(1)

    await wrapper.setProps({
      messages: [
        firstMessage,
        { id: 2, role: 'assistant', content: '第二条' },
        { id: 3, role: 'assistant', content: '第三条' }
      ]
    })
    await flushPromises()
    expect(frameQueue).toHaveLength(1)
    wrapper.unmount()
  })

  it('keeps message transitions disabled while history is hydrating', async () => {
    const wrapper = mountChat({
      messages: [{ id: 1, role: 'assistant', content: '已有记录' }]
    })

    expect(wrapper.get('.message-stack').classes()).toContain('message-stack--hydrating')
    drainFrames()
    await nextTick()
    expect(wrapper.get('.message-stack').classes()).not.toContain('message-stack--hydrating')

    await wrapper.setProps({ sessionId: 8, sessionStatus: 'loading', messages: [] })
    expect(wrapper.get('.message-stack').classes()).toContain('message-stack--hydrating')

    await wrapper.setProps({
      sessionStatus: 'ready',
      messages: [
        { id: 4, role: 'user', content: '历史问题' },
        { id: 5, role: 'assistant', content: '历史回答' }
      ]
    })
    await flushPromises()
    expect(wrapper.findAll('.msg-row')).toHaveLength(2)
    expect(wrapper.get('.message-stack').classes()).toContain('message-stack--hydrating')

    drainFrames()
    await nextTick()
    expect(wrapper.get('.message-stack').classes()).not.toContain('message-stack--hydrating')
    wrapper.unmount()
  })
})
