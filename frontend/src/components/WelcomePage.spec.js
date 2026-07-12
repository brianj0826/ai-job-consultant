import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const authMocks = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn()
}))

vi.mock('../api', () => ({
  getErrorMessage: vi.fn((_error, fallback) => fallback)
}))
vi.mock('../composables/useAuth', () => ({
  useAuth: () => authMocks
}))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn() }
}))

import WelcomePage from './WelcomePage.vue'

const ElFormStub = defineComponent({
  name: 'ElForm',
  emits: ['submit'],
  setup(_props, { emit, expose, slots }) {
    expose({
      clearValidate: vi.fn(),
      validate: vi.fn().mockResolvedValue(true)
    })
    return () => h('form', {
      onSubmit: (event) => emit('submit', event)
    }, slots.default?.())
  }
})

const stubs = {
  ElButton: {
    props: {
      disabled: Boolean,
      loading: Boolean,
      nativeType: { type: String, default: 'button' }
    },
    template: '<button :type="nativeType" :disabled="disabled || loading"><slot /></button>'
  },
  ElForm: ElFormStub,
  ElFormItem: { template: '<label><slot /></label>' },
  ElIcon: { template: '<span><slot /></span>' },
  ElInput: {
    inheritAttrs: false,
    props: { modelValue: { type: String, default: '' } },
    emits: ['update:modelValue'],
    template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  },
  ElLink: { template: '<a href="#"><slot /></a>' }
}

describe('WelcomePage', () => {
  beforeEach(() => {
    authMocks.login.mockReset()
    authMocks.login.mockResolvedValue({ id: 1, username: 'tester' })
    authMocks.register.mockReset()
  })

  it('submits once through the form and does not also handle Enter keyup', async () => {
    const wrapper = mount(WelcomePage, { global: { stubs } })

    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(authMocks.login).toHaveBeenCalledTimes(1)

    await wrapper.get('input').trigger('keyup.enter')
    await flushPromises()
    expect(authMocks.login).toHaveBeenCalledTimes(1)
    expect(wrapper.get('button[type="submit"]').exists()).toBe(true)
  })
})
