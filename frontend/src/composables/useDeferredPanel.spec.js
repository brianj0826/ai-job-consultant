import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useDeferredPanel } from './useDeferredPanel'

describe('useDeferredPanel', () => {
  it('waits for an async component ref before opening it', async () => {
    const panel = useDeferredPanel()
    const open = vi.fn()

    panel.requestOpen()
    expect(panel.mounted.value).toBe(true)
    expect(panel.pending.value).toBe(true)

    panel.componentRef.value = { open }
    await nextTick()

    expect(open).toHaveBeenCalledTimes(1)
    expect(panel.pending.value).toBe(false)
  })

  it('opens an already-mounted panel for subsequent requests', async () => {
    const panel = useDeferredPanel()
    const open = vi.fn()
    panel.componentRef.value = { open }
    await nextTick()

    panel.requestOpen()
    await nextTick()

    expect(open).toHaveBeenCalledTimes(1)
  })
})
