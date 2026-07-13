import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import InterviewBar from './InterviewBar.vue'

const stubs = {
  ElButton: { template: '<button type="button"><slot /></button>' },
  ElIcon: { template: '<span><slot /></span>' },
  ElProgress: { template: '<div class="progress-stub"></div>' }
}

describe('InterviewBar', () => {
  it('shows a real zero score and hides unresolved score values', async () => {
    const wrapper = mount(InterviewBar, {
      props: { active: true, score: 0 },
      global: { stubs }
    })

    expect(wrapper.get('.interview-score').text()).toContain('0 / 100')

    for (const score of [null, '', '   ']) {
      await wrapper.setProps({ score })
      expect(wrapper.find('.interview-score').exists()).toBe(false)
    }
  })
})
