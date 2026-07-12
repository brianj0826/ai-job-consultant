import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  createCareerResource: vi.fn(),
  createInterviewQuestion: vi.fn(),
  deleteCareerData: vi.fn(),
  deleteCareerResource: vi.fn(),
  deleteInterviewQuestion: vi.fn(),
  exportCareerData: vi.fn(),
  getCareerResource: vi.fn(),
  getCareerResources: vi.fn(),
  getErrorMessage: vi.fn((error, fallback) => error?.message || fallback),
  updateCareerResource: vi.fn(),
  updateInterviewQuestion: vi.fn()
}))

const message = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))

vi.mock('../../api', () => api)
vi.mock('element-plus', () => ({
  ElMessage: message,
  ElMessageBox: { confirm: vi.fn(), prompt: vi.fn() }
}))

import CareerResourceView from './CareerResourceView.vue'

const stubs = {
  CareerLayout: {
    props: ['title', 'eyebrow', 'description'],
    template: '<div><slot name="actions" /><slot /></div>'
  },
  InterviewBar: {
    props: ['active', 'title', 'status', 'current', 'total', 'score'],
    template: '<div data-testid="interview-bar">{{ title }} · {{ status }} · {{ total }}</div>'
  },
  RouterLink: { props: ['to'], template: '<a href="#"><slot /></a>' },
  ElButton: {
    props: ['disabled', 'loading', 'nativeType'],
    emits: ['click'],
    template: '<button :type="nativeType || \'button\'" :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>'
  },
  ElIcon: { template: '<span><slot /></span>' },
  ElInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>'
  },
  ElOption: { template: '<option><slot /></option>' },
  ElProgress: { props: ['percentage'], template: '<div>{{ percentage }}%</div>' },
  ElSelect: { template: '<select><slot /></select>' },
  ElSwitch: { template: '<input type="checkbox" />' }
}

const mountView = (resource) => mount(CareerResourceView, {
  props: { resource },
  global: { stubs }
})

describe('CareerResourceView', () => {
  beforeEach(() => {
    Object.values(api).forEach((mock) => mock.mockReset?.())
    api.getErrorMessage.mockImplementation((error, fallback) => error?.message || fallback)
    Object.values(message).forEach((mock) => mock.mockReset())
  })

  it('renders persisted report records returned by the career API', async () => {
    api.getCareerResources.mockResolvedValue({
      data: {
        items: [{
          id: 8,
          kind: 'job_match',
          title: 'AI 产品经理岗位匹配',
          summary: '优势是产品落地经验，下一步补充数据分析证据。',
          created_at: '2026-07-12T10:00:00Z'
        }],
        total: 1
      }
    })

    const wrapper = mountView('reports')
    await flushPromises()

    expect(api.getCareerResources).toHaveBeenCalledWith('reports')
    expect(wrapper.text()).toContain('AI 产品经理岗位匹配')
    expect(wrapper.text()).toContain('优势是产品落地经验')
    expect(wrapper.text()).toContain('岗位匹配')
  })

  it('shows a recoverable load error and retries in place', async () => {
    api.getCareerResources
      .mockRejectedValueOnce(new Error('职业数据服务暂不可用'))
      .mockResolvedValueOnce({ data: { items: [], total: 0 } })

    const wrapper = mountView('skills')
    await flushPromises()

    expect(wrapper.text()).toContain('职业数据服务暂不可用')
    const retry = wrapper.findAll('button').find((button) => button.text().includes('重试'))
    await retry.trigger('click')
    await flushPromises()

    expect(api.getCareerResources).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('还没有技能目标')
  })

  it('loads interview detail and connects it to InterviewBar', async () => {
    api.getCareerResources.mockImplementation((resource) => Promise.resolve({
      data: resource === 'jobs'
        ? { items: [{ id: 5, title: '产品经理', company: '示例公司' }], total: 1 }
        : { items: [{ id: 3, title: '产品经理模拟面试', status: 'planned', total_questions: 1 }], total: 1 }
    }))
    api.getCareerResource.mockResolvedValue({
      data: {
        id: 3,
        title: '产品经理模拟面试',
        status: 'in_progress',
        current_question: 1,
        total_questions: 1,
        questions: [{ id: 9, position: 1, question: '请介绍一个项目', answer: '', feedback: '' }]
      }
    })

    const wrapper = mountView('interviews')
    await flushPromises()
    const manage = wrapper.findAll('button').find((button) => button.text().includes('管理'))
    await manage.trigger('click')
    await flushPromises()

    expect(api.getCareerResource).toHaveBeenCalledWith('interviews', 3)
    expect(wrapper.get('[data-testid="interview-bar"]').text()).toContain('in_progress')
    expect(wrapper.text()).toContain('请介绍一个项目')
  })
})
