import { readonly, ref, watch } from 'vue'

export const useDeferredPanel = (method = 'open') => {
  const componentRef = ref(null)
  const mounted = ref(false)
  const pending = ref(false)

  const requestOpen = () => {
    mounted.value = true
    pending.value = true
  }

  watch([componentRef, pending], ([instance, shouldOpen]) => {
    if (!instance || !shouldOpen || typeof instance[method] !== 'function') return
    pending.value = false
    instance[method]()
  }, { flush: 'post' })

  return {
    componentRef,
    mounted: readonly(mounted),
    pending: readonly(pending),
    requestOpen
  }
}
