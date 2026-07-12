import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import JobMatchPanel from './JobMatchPanel.vue'
import ResumeReport from './ResumeReport.vue'

const stubs = {
  InsightDrawerShell: {
    props: ['modelValue'],
    template: `
      <div>
        <slot name="header" title-id="drawer-title" title-class="drawer-title"></slot>
        <slot></slot>
      </div>
    `
  },
  ElIcon: { template: '<span><slot /></span>' },
  ElProgress: { template: '<div class="progress-stub"><slot :percentage="percentage" /></div>', props: ['percentage'] },
  ElTag: { template: '<span><slot /></span>' }
}

describe('insight panel parsing', () => {
  it('parses a labeled x/10 resume score without treating unrelated minutes as a score', async () => {
    const wrapper = mount(ResumeReport, {
      props: { reportText: '综合评分：8/10 分\n\n## 优点\n表达清晰。' },
      global: { stubs }
    })

    expect(wrapper.get('.score-value').text()).toContain('8')
    expect(wrapper.get('#drawer-title').text()).toBe('简历分析报告')

    await wrapper.setProps({ reportText: '建议用 10 分钟重新梳理项目背景。' })
    expect(wrapper.find('.score-overview').exists()).toBe(false)
    expect(wrapper.get('.score-unavailable').text()).toContain('未解析到综合评分')
  })

  it('stops skill extraction at markdown headings without requiring a colon', () => {
    const wrapper = mount(JobMatchPanel, {
      props: {
        reportText: [
          '匹配度：82%',
          '## 匹配的技能',
          '- Vue',
          '- TypeScript',
          '## 缺失的技能',
          '- Kubernetes',
          '## 建议',
          '- 补充云原生项目经验'
        ].join('\n')
      },
      global: { stubs }
    })

    expect(wrapper.get('.skill-card--matched').text()).toContain('Vue')
    expect(wrapper.get('.skill-card--matched').text()).toContain('TypeScript')
    expect(wrapper.get('.skill-card--matched').text()).not.toContain('Kubernetes')
    expect(wrapper.get('.skill-card--missing').text()).toContain('Kubernetes')
    expect(wrapper.get('.skill-card--missing').text()).not.toContain('云原生项目经验')
    expect(wrapper.get('#drawer-title').text()).toBe('岗位匹配分析')
  })
})
