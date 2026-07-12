import { describe, expect, it } from 'vitest'

import {
  enhanceMarkdownScrollRegions,
  renderAccessibleHtml,
  renderAccessibleMarkdown
} from './markdownAccessibility'

const parseHtml = (html) => {
  const template = document.createElement('template')
  template.innerHTML = html
  return template.content
}

describe('markdown accessibility', () => {
  it('sanitizes Markdown before making code and table scroll regions keyboard reachable', () => {
    const html = renderAccessibleMarkdown([
      '<script>window.exposed = true</script>',
      '<img src="x" onerror="window.exposed = true">',
      '',
      '```js',
      'const result = "a very long line"',
      '```',
      '',
      '| 项目 | 结果 |',
      '| --- | --- |',
      '| A | B |'
    ].join('\n'))
    const content = parseHtml(html)
    const code = content.querySelector('pre')
    const table = content.querySelector('table')

    expect(content.querySelector('script')).toBeNull()
    expect(content.querySelector('img').hasAttribute('onerror')).toBe(false)
    expect(code.getAttribute('tabindex')).toBe('0')
    expect(code.getAttribute('aria-label')).toBe('代码块，可横向滚动')
    expect(table.getAttribute('tabindex')).toBe('0')
    expect(table.getAttribute('aria-label')).toBe('数据表格，可横向滚动')
  })

  it('uses context labels and sanitizes already-rendered streaming HTML', () => {
    const html = renderAccessibleHtml(
      '<pre onclick="alert(1)"><code>output</code></pre><table><tbody><tr><td>A</td></tr></tbody></table>',
      { code: '简历代码', table: '简历表格' }
    )
    const content = parseHtml(html)

    expect(content.querySelector('pre').hasAttribute('onclick')).toBe(false)
    expect(content.querySelector('pre').getAttribute('aria-label')).toBe('简历代码')
    expect(content.querySelector('table').getAttribute('aria-label')).toBe('简历表格')
  })

  it('leaves sanitized HTML unchanged when DOM APIs are unavailable', () => {
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'document')
    Object.defineProperty(globalThis, 'document', { configurable: true, value: undefined })

    try {
      expect(enhanceMarkdownScrollRegions('<p>安全内容</p>')).toBe('<p>安全内容</p>')
    } finally {
      Object.defineProperty(globalThis, 'document', descriptor)
    }
  })
})
