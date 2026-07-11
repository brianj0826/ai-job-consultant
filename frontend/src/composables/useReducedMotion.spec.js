import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { useReducedMotion } from './useReducedMotion'

const createMediaQuery = (initialMatches) => {
  const listeners = new Set()
  const mediaQuery = {
    matches: initialMatches,
    media: '(prefers-reduced-motion: reduce)',
    addEventListener: vi.fn((type, listener) => {
      if (type === 'change') listeners.add(listener)
    }),
    removeEventListener: vi.fn((type, listener) => {
      if (type === 'change') listeners.delete(listener)
    }),
    setMatches(matches) {
      this.matches = matches
      listeners.forEach((listener) => listener({ matches, media: this.media }))
    }
  }

  return mediaQuery
}

const mountHarness = () => mount({
  setup: useReducedMotion,
  template: '<span>{{ prefersReducedMotion }}</span>'
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useReducedMotion', () => {
  it('tracks the current media-query preference and removes its listener', async () => {
    const mediaQuery = createMediaQuery(true)
    const matchMedia = vi.fn(() => mediaQuery)
    vi.stubGlobal('matchMedia', matchMedia)

    const wrapper = mountHarness()

    expect(matchMedia).toHaveBeenCalledWith('(prefers-reduced-motion: reduce)')
    expect(wrapper.text()).toBe('true')
    expect(mediaQuery.addEventListener).toHaveBeenCalledWith('change', expect.any(Function))

    mediaQuery.setMatches(false)
    await nextTick()
    expect(wrapper.text()).toBe('false')

    wrapper.unmount()
    expect(mediaQuery.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function))
  })

  it('defaults to no preference when matchMedia is unavailable', () => {
    vi.stubGlobal('matchMedia', undefined)

    const wrapper = mountHarness()

    expect(wrapper.text()).toBe('false')
    wrapper.unmount()
  })
})
