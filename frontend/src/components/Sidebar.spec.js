import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  deleteSource: vi.fn(),
  fetchUrlContent: vi.fn(),
  getDocStatus: vi.fn(),
  getMessages: vi.fn(),
  getSessions: vi.fn(),
  renameSession: vi.fn(),
  uploadPDF: vi.fn()
}))

const message = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  warning: vi.fn()
}))

vi.mock('../api', () => api)
vi.mock('element-plus', () => ({
  ElMessage: message,
  ElMessageBox: {
    confirm: vi.fn(),
    prompt: vi.fn()
  }
}))

import Sidebar from './Sidebar.vue'

const stubs = {
  ElButton: {
    props: ['disabled', 'loading'],
    emits: ['click'],
    template: '<button :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>'
  },
  ElCollapse: { template: '<div><slot /></div>' },
  ElCollapseItem: { template: '<section><slot name="title" /><slot /></section>' },
  ElIcon: { template: '<span><slot /></span>' },
  ElInput: { template: '<textarea></textarea>' },
  ElOption: { template: '<option></option>' },
  ElSelect: { template: '<select><slot /></select>' },
  ElSwitch: { template: '<button type="button"></button>' },
  ElTag: { template: '<span><slot /></span>' },
  ElUpload: { template: '<div><slot /></div>' }
}

const mountSidebar = () => mount(Sidebar, {
  props: {
    currentUsername: '测试用户',
    userId: 7
  },
  global: { stubs }
})

describe('Sidebar knowledge states', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    Object.values(api).forEach((mock) => mock.mockReset())
    Object.values(message).forEach((mock) => mock.mockReset())
    api.getSessions.mockResolvedValue({ data: [{ id: 101, name: '测试会话' }] })
    api.getMessages.mockResolvedValue({ data: [] })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a load error instead of a false empty state', async () => {
    api.getDocStatus.mockRejectedValue({
      response: { data: { detail: '知识库服务不可用' } }
    })

    const wrapper = mountSidebar()
    await flushPromises()

    expect(wrapper.text()).toContain('知识库加载失败')
    expect(wrapper.text()).not.toContain('知识库为空')
    wrapper.unmount()
  })

  it('keeps the last successful snapshot when a refresh fails', async () => {
    api.getDocStatus.mockResolvedValueOnce({
      data: {
        doc_count: 3,
        sources: [{ type: 'file', source: 'resume.pdf' }]
      }
    })

    const wrapper = mountSidebar()
    await flushPromises()
    expect(wrapper.text()).toContain('3 个文档块')
    expect(wrapper.text()).toContain('resume.pdf')

    api.getDocStatus.mockRejectedValueOnce({
      response: { data: { detail: '刷新失败' } }
    })
    await wrapper.vm.loadDocStatus()
    await flushPromises()

    expect(wrapper.text()).toContain('3 个文档块')
    expect(wrapper.text()).toContain('resume.pdf')
    expect(wrapper.text()).toContain('刷新失败，当前仍显示上次加载的数据。')
    wrapper.unmount()
  })
})
