import DOMPurify from 'dompurify'
import { marked } from 'marked'

const DEFAULT_LABELS = Object.freeze({
  code: '代码块，可横向滚动',
  table: '数据表格，可横向滚动'
})

export const enhanceMarkdownScrollRegions = (sanitizedHtml, labels = {}) => {
  if (!sanitizedHtml || typeof document === 'undefined') return sanitizedHtml

  const regionLabels = { ...DEFAULT_LABELS, ...labels }
  const template = document.createElement('template')
  template.innerHTML = sanitizedHtml

  template.content.querySelectorAll('pre').forEach((region) => {
    region.setAttribute('tabindex', '0')
    region.setAttribute('aria-label', regionLabels.code)
  })

  template.content.querySelectorAll('table').forEach((region) => {
    region.setAttribute('tabindex', '0')
    region.setAttribute('aria-label', regionLabels.table)
  })

  return template.innerHTML
}

export const renderAccessibleHtml = (html, labels) => {
  if (!html || typeof DOMPurify.sanitize !== 'function') return ''
  return enhanceMarkdownScrollRegions(DOMPurify.sanitize(html), labels)
}

export const renderAccessibleMarkdown = (markdown, labels) => {
  if (!markdown || typeof DOMPurify.sanitize !== 'function') return ''
  return renderAccessibleHtml(marked(markdown), labels)
}
