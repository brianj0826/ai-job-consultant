import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const renderMarkdown = vi.hoisted(() => vi.fn((text) => `<p>${text}</p>`))

vi.mock('marked', () => ({ marked: renderMarkdown }))

import MessageBubble from './MessageBubble.vue'

const globalStubs = {
  ElButton: {
    emits: ['click'],
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>'
  },
  ElIcon: { template: '<span><slot /></span>' },
  ElTag: { template: '<span><slot /></span>' }
}

describe('MessageBubble', () => {
  it('keeps completed Markdown cached when sibling state changes', async () => {
    renderMarkdown.mockClear()
    const message = {
      id: 17,
      role: 'assistant',
      content: '**稳定内容**',
      timestamp: '2026-01-01T08:00:00.000Z'
    }
    const wrapper = mount(MessageBubble, {
      props: { message, feedbackValue: null },
      global: { stubs: globalStubs }
    })

    expect(renderMarkdown).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.message-content').html()).toContain('稳定内容')

    await wrapper.setProps({ feedbackValue: 'like' })
    await wrapper.setProps({ message: { ...message } })

    expect(renderMarkdown).toHaveBeenCalledTimes(1)
  })

  it('renders an interrupted reply and retries from the same bubble', async () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: { role: 'assistant', content: '部分回复' },
        renderedHtml: '<p>部分回复</p>',
        interrupted: true,
        error: '网络连接中断'
      },
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('部分回复')
    expect(wrapper.text()).toContain('网络连接中断')

    await wrapper.get('.inline-interruption button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
})
