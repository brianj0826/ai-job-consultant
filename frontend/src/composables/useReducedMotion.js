import { onBeforeUnmount, onMounted, readonly, ref } from 'vue'

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

const getMediaQuery = () => {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return null
  return window.matchMedia(REDUCED_MOTION_QUERY)
}

export const useReducedMotion = () => {
  let mediaQuery = getMediaQuery()
  let removePreferenceListener = null
  const prefersReducedMotion = ref(mediaQuery?.matches ?? false)

  const syncPreference = (event) => {
    prefersReducedMotion.value = event.matches
  }

  onMounted(() => {
    mediaQuery ||= getMediaQuery()
    if (!mediaQuery) return

    syncPreference(mediaQuery)

    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', syncPreference)
      removePreferenceListener = () => mediaQuery?.removeEventListener('change', syncPreference)
    } else if (typeof mediaQuery.addListener === 'function') {
      mediaQuery.addListener(syncPreference)
      removePreferenceListener = () => mediaQuery?.removeListener(syncPreference)
    }
  })

  onBeforeUnmount(() => {
    removePreferenceListener?.()
    removePreferenceListener = null
    mediaQuery = null
  })

  return {
    prefersReducedMotion: readonly(prefersReducedMotion)
  }
}
