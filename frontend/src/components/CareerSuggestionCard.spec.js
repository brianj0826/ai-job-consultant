import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  acceptCareerSuggestion: vi.fn(),
  dismissCareerSuggestion: vi.fn(),
  getCareerResource: vi.fn(),
  getErrorMessage: vi.fn((error, fallback) => error?.message || fallback),
  restoreCareerSuggestion: vi.fn(),
  updateCareerSuggestion: vi.fn()
}))
const routerPush = vi.hoisted(() => vi.fn())

vi.mock('../api', () => apiMocks)
vi.mock('vue-router', () => ({ useRouter: () => ({ push: routerPush }) }))

import CareerSuggestionCard from './CareerSuggestionCard.vue'

const resourcePayloads = {
  resumes: { title: '前端简历', content: '完整简历正文' },
  jobs: { title: '高级前端工程师', description: '完整职位描述', status: 'saved' },
  applications: { job_id: 3, stage: 'applied' },
  interviews: { title: '一轮模拟面试', status: 'planned' },
  reports: { kind: 'career_plan', title: '成长计划', summary: '下一步行动', payload: { schema_version: 1 } },
  skills: { skill: 'Redis', status: 'planned', progress: 0 },
  interview_questions: {
    interview_id: 8,
    questions: [{ question: '如何设计缓存？', reference_answer: '先明确一致性要求', coaching_notes: '分层回答' }]
  }
}

const makeSuggestion = (resourceType = 'skills', overrides = {}) => ({
  id: 41,
  action: 'create',
  resource_type: resourceType,
  title: `添加${resourceType}`,
  reason: '对话中出现了可执行的职业计划。',
  payload: resourcePayloads[resourceType],
  relation_hints: {},
  status: 'pending',
  revision: 2,
  source_message_id: 10,
  ...overrides
})

const stubs = {
  ElButton: {
    props: { disabled: Boolean, loading: Boolean },
    emits: ['click'],
    template: '<button type="button" :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>'
  },
  ElIcon: { template: '<span><slot /></span>' },
  ElTag: { template: '<span><slot /></span>' },
  CareerSuggestionEditor: {
    props: ['modelValue', 'suggestion', 'saving'],
    emits: ['update:modelValue', 'save'],
    template: '<button class="editor-save" type="button" @click="$emit(\'save\', { skill: \'Redis\', status: \'planned\', progress: 0 })">保存编辑</button>'
  }
}

const mountCard = (suggestion) => mount(CareerSuggestionCard, {
  props: { suggestion },
  global: { stubs }
})

describe('CareerSuggestionCard', () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mock) => mock.mockClear())
    routerPush.mockReset()
  })

  it.each(Object.keys(resourcePayloads))('renders the %s suggestion type', (resourceType) => {
    const wrapper = mountCard(makeSuggestion(resourceType))
    expect(wrapper.get('.suggestion-card').attributes('aria-busy')).toBe('false')
    expect(wrapper.text()).toContain('待确认')
    expect(wrapper.text()).toContain('确认添加')
    wrapper.unmount()
  })

  it('accepts once with the current revision and emits the authoritative state', async () => {
    let resolveAccept
    apiMocks.acceptCareerSuggestion.mockImplementation(() => new Promise((resolve) => {
      resolveAccept = resolve
    }))
    const wrapper = mountCard(makeSuggestion())
    const acceptButton = wrapper.findAll('button').find((button) => button.text().includes('确认添加'))

    await acceptButton.trigger('click')
    await acceptButton.trigger('click')
    expect(apiMocks.acceptCareerSuggestion).toHaveBeenCalledTimes(1)
    expect(apiMocks.acceptCareerSuggestion).toHaveBeenCalledWith(41, 2)

    resolveAccept({
      data: makeSuggestion('skills', {
        status: 'accepted',
        revision: 3,
        created_resource: { resource_type: 'skills', ids: [91], id: 91 }
      })
    })
    await flushPromises()

    expect(wrapper.text()).toContain('已添加到技能计划')
    expect(wrapper.emitted('update')[0][0]).toMatchObject({ status: 'accepted', revision: 3 })
    wrapper.unmount()
  })

  it('persists edited payloads without calling generic career create APIs', async () => {
    apiMocks.updateCareerSuggestion.mockResolvedValue({
      data: makeSuggestion('skills', {
        revision: 3,
        payload: { skill: 'Redis', status: 'planned', progress: 0 }
      })
    })
    const wrapper = mountCard(makeSuggestion())

    await wrapper.get('.editor-save').trigger('click')
    await flushPromises()

    expect(apiMocks.updateCareerSuggestion).toHaveBeenCalledWith(41, 2, {
      skill: 'Redis', status: 'planned', progress: 0
    })
    expect(wrapper.emitted('update')[0][0].revision).toBe(3)
    wrapper.unmount()
  })

  it('restores ignored suggestions and reports a deleted accepted resource', async () => {
    apiMocks.restoreCareerSuggestion.mockResolvedValue({
      data: makeSuggestion('jobs', { status: 'pending', revision: 4 })
    })
    const wrapper = mountCard(makeSuggestion('jobs', { status: 'dismissed', revision: 3 }))
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(apiMocks.restoreCareerSuggestion).toHaveBeenCalledWith(41, 3)
    wrapper.unmount()

    apiMocks.getCareerResource.mockRejectedValue({ status: 404 })
    const accepted = mountCard(makeSuggestion('jobs', {
      status: 'accepted',
      created_resource: { resource_type: 'jobs', ids: [77], id: 77 }
    }))
    await accepted.get('.suggestion-card__resource-link').trigger('click')
    await flushPromises()
    expect(accepted.text()).toContain('记录已被删除')
    expect(routerPush).not.toHaveBeenCalled()
    accepted.unmount()
  })

  it('opens an accepted question batch at its interview instead of a question id', async () => {
    apiMocks.getCareerResource.mockResolvedValue({ data: { id: 8 } })
    const wrapper = mountCard(makeSuggestion('interview_questions', {
      status: 'accepted',
      created_resource: { resource_type: 'interview_questions', ids: [301, 302] }
    }))

    await wrapper.get('.suggestion-card__resource-link').trigger('click')
    await flushPromises()

    expect(apiMocks.getCareerResource).toHaveBeenCalledWith('interviews', 8)
    expect(routerPush).toHaveBeenCalledWith({
      name: 'career-interviews',
      query: { highlight: '8' }
    })
    wrapper.unmount()
  })
})
