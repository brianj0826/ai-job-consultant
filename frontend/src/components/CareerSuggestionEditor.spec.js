import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getCareerResources: vi.fn(),
  getErrorMessage: vi.fn((error, fallback) => error?.message || fallback)
}))

vi.mock('../api', () => apiMocks)

import CareerSuggestionEditor from './CareerSuggestionEditor.vue'

const stubs = {
  ElDialog: {
    props: ['modelValue', 'title'],
    emits: ['update:modelValue', 'opened'],
    template: '<section><h2>{{ title }}</h2><slot /><slot name="footer" /></section>'
  },
  ElButton: {
    props: { disabled: Boolean, loading: Boolean },
    emits: ['click'],
    template: '<button type="button" :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>'
  },
  ElInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  },
  ElSelect: {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', Number($event.target.value)); $emit(\'change\', Number($event.target.value))"><slot /></select>'
  },
  ElOption: {
    props: ['value', 'label'],
    template: '<option :value="value">{{ label }}</option>'
  }
}

describe('CareerSuggestionEditor', () => {
  beforeEach(() => {
    apiMocks.getCareerResources.mockReset()
    apiMocks.getCareerResources.mockResolvedValue({ data: [{ id: 8, title: '前端模拟面试' }] })
  })

  it('serializes an interview-question batch without user answer, feedback, or score', async () => {
    const wrapper = mount(CareerSuggestionEditor, {
      props: {
        modelValue: true,
        suggestion: {
          id: 21,
          resource_type: 'interview_questions',
          payload: {
            interview_id: 8,
            questions: [
              { question: '缓存击穿是什么？', reference_answer: '热点 key 失效', coaching_notes: '先定义再给方案' },
              { question: '如何限流？', reference_answer: '令牌桶', coaching_notes: '说明取舍' }
            ]
          }
        }
      },
      global: { stubs }
    })
    await flushPromises()

    const saveButton = wrapper.findAll('button').find((button) => button.text().includes('保存草稿'))
    await saveButton.trigger('click')

    const payload = wrapper.emitted('save')[0][0]
    expect(payload).toEqual({
      interview_id: 8,
      questions: [
        { question: '缓存击穿是什么？', reference_answer: '热点 key 失效', coaching_notes: '先定义再给方案' },
        { question: '如何限流？', reference_answer: '令牌桶', coaching_notes: '说明取舍' }
      ]
    })
    payload.questions.forEach((question) => {
      expect(question).not.toHaveProperty('answer')
      expect(question).not.toHaveProperty('feedback')
      expect(question).not.toHaveProperty('score')
    })
    wrapper.unmount()
  })

  it('keeps report structured payload as JSON and clears an empty relation pair', async () => {
    const wrapper = mount(CareerSuggestionEditor, {
      props: {
        modelValue: true,
        suggestion: {
          id: 22,
          resource_type: 'reports',
          payload: {
            kind: 'career_plan',
            title: '职业计划',
            entity_type: '',
            entity_id: null,
            summary: '优先学习 Redis',
            payload: { schema_version: 1, actions: ['Redis'] }
          }
        }
      },
      global: { stubs }
    })
    await flushPromises()

    const saveButton = wrapper.findAll('button').find((button) => button.text().includes('保存草稿'))
    await saveButton.trigger('click')
    const payload = wrapper.emitted('save')[0][0]
    expect(payload.payload).toEqual({ schema_version: 1, actions: ['Redis'] })
    expect(payload.entity_type).toBeNull()
    expect(payload.entity_id).toBeNull()
    wrapper.unmount()
  })
})
