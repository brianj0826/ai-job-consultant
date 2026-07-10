import { computed, readonly, ref } from 'vue'
import {
  changePassword as changePasswordRequest,
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest
} from '../api'
import {
  setPasswordChangeRequiredHandler,
  setUnauthorizedHandler
} from '../api/client'

const user = ref(null)
const status = ref('idle')
const error = ref(null)
const lastRemoteAuthChange = ref(null)
let bootstrapPromise = null
let remoteAuthSequence = 0
let authStateEpoch = 0

const AUTH_SYNC_CHANNEL = 'ai-job-consultant-auth'
const AUTH_SYNC_STORAGE_KEY = 'ai_auth_sync_event'
const AUTH_SYNC_MESSAGE_TYPE = 'auth-state-changed'
const AUTH_SYNC_VERSION = 1
const AUTH_SYNC_REASONS = new Set(['login', 'register', 'logout', 'change-password'])
const AUTH_SYNC_RESET_REASONS = new Set(['login', 'register', 'logout'])

let authSyncChannel = null
let authSyncStarted = false

const normalizeUser = (value) => {
  if (!value || value.id === undefined || !value.username) return null
  return {
    ...value,
    id: Number(value.id),
    role: value.role || 'user',
    status: value.status || 'active',
    must_change_password: Boolean(value.must_change_password)
  }
}

const clearLegacyIdentity = () => {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.removeItem('ai_user_id')
    localStorage.removeItem('ai_username')
  } catch {
    // Authentication must not depend on optional browser storage access.
  }
}

export const setAuthenticatedUser = (value) => {
  const normalized = normalizeUser(value)
  authStateEpoch += 1
  user.value = normalized
  status.value = normalized ? 'authenticated' : 'anonymous'
  error.value = null
  clearLegacyIdentity()
  return normalized
}

export const clearAuth = () => {
  authStateEpoch += 1
  user.value = null
  status.value = 'anonymous'
  error.value = null
  clearLegacyIdentity()
}

export const markPasswordChangeRequired = () => {
  if (!user.value) return
  authStateEpoch += 1
  user.value = { ...user.value, must_change_password: true }
}

const createSyncId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    try {
      return crypto.randomUUID()
    } catch {
      // Fall back when randomUUID is unavailable in an insecure context.
    }
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

const validSyncMessage = (value) => (
  value
  && value.version === AUTH_SYNC_VERSION
  && value.type === AUTH_SYNC_MESSAGE_TYPE
  && typeof value.id === 'string'
  && AUTH_SYNC_REASONS.has(value.reason)
)

const publishAuthChange = (reason) => {
  if (!AUTH_SYNC_REASONS.has(reason) || typeof window === 'undefined') return
  const message = {
    id: createSyncId(),
    reason,
    type: AUTH_SYNC_MESSAGE_TYPE,
    version: AUTH_SYNC_VERSION
  }

  if (authSyncChannel) {
    try {
      authSyncChannel.postMessage(message)
      return
    } catch {
      // Fall through to the storage event transport when BroadcastChannel fails.
    }
  }

  // The fallback deliberately contains no user data or credentials. Other tabs
  // always re-read /me instead of trusting values from browser storage.
  try {
    window.localStorage.setItem(AUTH_SYNC_STORAGE_KEY, JSON.stringify(message))
    window.localStorage.removeItem(AUTH_SYNC_STORAGE_KEY)
  } catch {
    // Visibility revalidation remains available when storage is unavailable.
  }
}

const synchronizeFromServer = async (message) => {
  if (!validSyncMessage(message)) return
  if (AUTH_SYNC_RESET_REASONS.has(message.reason)) clearAuth()
  try {
    await bootstrapAuth({ force: true })
  } catch {
    // A transient revalidation error is reflected by auth state; the next
    // visibility event will retry without trusting the broadcast payload.
  } finally {
    lastRemoteAuthChange.value = {
      reason: message.reason,
      sequence: ++remoteAuthSequence
    }
  }
}

const handleBroadcastMessage = (event) => {
  void synchronizeFromServer(event?.data)
}

const handleStorageMessage = (event) => {
  if (event.key !== AUTH_SYNC_STORAGE_KEY || !event.newValue) return
  try {
    void synchronizeFromServer(JSON.parse(event.newValue))
  } catch {
    // Ignore malformed same-origin storage events.
  }
}

const handleVisibilityChange = () => {
  if (document.visibilityState !== 'visible') return
  void bootstrapAuth({ force: true }).catch(() => undefined)
}

export const startAuthSynchronization = () => {
  if (authSyncStarted || typeof window === 'undefined' || typeof document === 'undefined') return
  authSyncStarted = true

  window.addEventListener('storage', handleStorageMessage)
  document.addEventListener('visibilitychange', handleVisibilityChange)

  if (typeof window.BroadcastChannel === 'function') {
    try {
      authSyncChannel = new window.BroadcastChannel(AUTH_SYNC_CHANNEL)
      authSyncChannel.addEventListener('message', handleBroadcastMessage)
    } catch {
      authSyncChannel = null
    }
  }
}

export const stopAuthSynchronization = () => {
  if (!authSyncStarted || typeof window === 'undefined' || typeof document === 'undefined') return
  window.removeEventListener('storage', handleStorageMessage)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  authSyncChannel?.removeEventListener?.('message', handleBroadcastMessage)
  authSyncChannel?.close?.()
  authSyncChannel = null
  authSyncStarted = false
}

setUnauthorizedHandler(clearAuth)
setPasswordChangeRequiredHandler(markPasswordChangeRequired)

export const bootstrapAuth = async ({ force = false } = {}) => {
  if (bootstrapPromise) {
    if (!force) return bootstrapPromise
    await bootstrapPromise.catch(() => undefined)
  }
  if (!force && status.value !== 'idle') return user.value

  const previousUser = user.value
  const preserveAuthenticatedState = status.value === 'authenticated' && Boolean(previousUser)
  const requestEpoch = authStateEpoch
  if (!preserveAuthenticatedState) status.value = 'loading'
  error.value = null
  bootstrapPromise = getCurrentUser()
    .then((response) => {
      if (requestEpoch !== authStateEpoch) return user.value
      return setAuthenticatedUser(response.data.user)
    })
    .catch((requestError) => {
      if (requestEpoch !== authStateEpoch) return user.value
      if (requestError.status === 401) {
        clearAuth()
        return null
      }
      if (preserveAuthenticatedState) {
        user.value = previousUser
        status.value = 'authenticated'
      } else {
        user.value = null
        status.value = 'error'
      }
      error.value = requestError
      throw requestError
    })
    .finally(() => {
      bootstrapPromise = null
    })

  return bootstrapPromise
}

export const useAuth = () => {
  const isAuthenticated = computed(() => status.value === 'authenticated' && Boolean(user.value))
  const isAdmin = computed(() => ['admin', 'super_admin'].includes(user.value?.role))
  const isSuperAdmin = computed(() => user.value?.role === 'super_admin')
  const mustChangePassword = computed(() => Boolean(user.value?.must_change_password))

  const login = async (username, password) => {
    status.value = 'loading'
    error.value = null
    try {
      const response = await loginRequest(username, password)
      const authenticatedUser = setAuthenticatedUser(response.data.user)
      publishAuthChange('login')
      return authenticatedUser
    } catch (requestError) {
      user.value = null
      status.value = 'anonymous'
      error.value = requestError
      throw requestError
    }
  }

  const register = async (username, password) => {
    status.value = 'loading'
    error.value = null
    try {
      const response = await registerRequest(username, password)
      const authenticatedUser = setAuthenticatedUser(response.data.user)
      publishAuthChange('register')
      return authenticatedUser
    } catch (requestError) {
      status.value = 'anonymous'
      error.value = requestError
      throw requestError
    }
  }

  const logout = async () => {
    error.value = null
    try {
      await logoutRequest()
      clearAuth()
      publishAuthChange('logout')
    } catch (requestError) {
      if (requestError.status === 401) {
        clearAuth()
        publishAuthChange('logout')
        return
      }
      error.value = requestError
      throw requestError
    }
  }

  const changePassword = async (currentPassword, newPassword) => {
    error.value = null
    try {
      const response = await changePasswordRequest(currentPassword, newPassword)
      const authenticatedUser = setAuthenticatedUser(response.data.user)
      publishAuthChange('change-password')
      return authenticatedUser
    } catch (requestError) {
      error.value = requestError
      throw requestError
    }
  }

  return {
    authError: readonly(error),
    authStatus: readonly(status),
    currentUser: readonly(user),
    isAdmin,
    isAuthenticated,
    isSuperAdmin,
    lastRemoteAuthChange: readonly(lastRemoteAuthChange),
    mustChangePassword,
    bootstrapAuth,
    changePassword,
    clearAuth,
    login,
    logout,
    register,
    setAuthenticatedUser
  }
}

export const resetAuthStateForTests = () => {
  stopAuthSynchronization()
  bootstrapPromise = null
  user.value = null
  status.value = 'idle'
  error.value = null
  lastRemoteAuthChange.value = null
  remoteAuthSequence = 0
  authStateEpoch = 0
}
