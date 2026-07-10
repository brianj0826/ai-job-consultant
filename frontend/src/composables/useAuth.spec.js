import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  changePassword: vi.fn(),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  register: vi.fn()
}))
const handlers = vi.hoisted(() => ({ password: null, unauthorized: null }))

vi.mock('../api', () => api)
vi.mock('../api/client', () => ({
  setPasswordChangeRequiredHandler: (handler) => { handlers.password = handler },
  setUnauthorizedHandler: (handler) => { handlers.unauthorized = handler }
}))

const authModule = await import('./useAuth.js')
const originalBroadcastChannelDescriptor = Object.getOwnPropertyDescriptor(window, 'BroadcastChannel')
const originalVisibilityStateDescriptor = Object.getOwnPropertyDescriptor(document, 'visibilityState')

const setBroadcastChannel = (value) => {
  Object.defineProperty(window, 'BroadcastChannel', {
    configurable: true,
    writable: true,
    value
  })
}

const restoreBrowserDescriptors = () => {
  if (originalBroadcastChannelDescriptor) {
    Object.defineProperty(window, 'BroadcastChannel', originalBroadcastChannelDescriptor)
  } else {
    delete window.BroadcastChannel
  }
  if (originalVisibilityStateDescriptor) {
    Object.defineProperty(document, 'visibilityState', originalVisibilityStateDescriptor)
  } else {
    delete document.visibilityState
  }
}

describe('useAuth', () => {
  beforeEach(() => {
    authModule.resetAuthStateForTests()
    Object.values(api).forEach((mock) => mock.mockReset())
    setBroadcastChannel(undefined)
    localStorage.setItem('ai_user_id', '99')
    localStorage.setItem('ai_username', 'legacy-user')
  })

  afterEach(() => {
    authModule.resetAuthStateForTests()
    vi.restoreAllMocks()
    restoreBrowserDescriptors()
  })

  it('normalizes the authenticated user and removes legacy identity storage', async () => {
    api.login.mockResolvedValue({ data: { user: { id: 7, username: 'career', role: 'admin', status: 'active' } } })
    const auth = authModule.useAuth()
    const user = await auth.login('career', 'secret123')

    expect(user).toMatchObject({ id: 7, role: 'admin', must_change_password: false })
    expect(auth.isAuthenticated.value).toBe(true)
    expect(auth.isAdmin.value).toBe(true)
    expect(localStorage.getItem('ai_user_id')).toBeNull()
  })

  it('returns to anonymous after a rejected login', async () => {
    api.login.mockRejectedValue({ status: 401 })
    const auth = authModule.useAuth()
    await expect(auth.login('career', 'wrong')).rejects.toMatchObject({ status: 401 })
    expect(auth.authStatus.value).toBe('anonymous')
    expect(auth.currentUser.value).toBeNull()
  })

  it('restores /me, changes the password, and revokes logout', async () => {
    api.getCurrentUser.mockResolvedValue({
      data: { user: { id: 8, username: 'forced', role: 'user', must_change_password: true } }
    })
    api.changePassword.mockResolvedValue({
      data: { user: { id: 8, username: 'forced', role: 'user', must_change_password: false } }
    })
    api.logout.mockResolvedValue({ data: { ok: true } })
    const auth = authModule.useAuth()

    await authModule.bootstrapAuth()
    expect(auth.mustChangePassword.value).toBe(true)
    await auth.changePassword('temporary', 'new-secret')
    expect(auth.mustChangePassword.value).toBe(false)
    await auth.logout()
    expect(api.logout).toHaveBeenCalledTimes(1)
    expect(auth.authStatus.value).toBe('anonymous')
  })

  it.each([0, 403, 500])('preserves the authenticated user when logout fails with status %s', async (status) => {
    const requestError = { status }
    api.logout.mockRejectedValue(requestError)
    authModule.setAuthenticatedUser({ id: 11, username: 'still-signed-in', role: 'user' })
    const auth = authModule.useAuth()

    await expect(auth.logout()).rejects.toBe(requestError)
    expect(auth.authStatus.value).toBe('authenticated')
    expect(auth.currentUser.value).toMatchObject({ id: 11, username: 'still-signed-in' })
    expect(auth.authError.value).toEqual(requestError)
  })

  it('treats an explicit logout 401 as an already-ended session', async () => {
    api.logout.mockRejectedValue({ status: 401 })
    authModule.setAuthenticatedUser({ id: 12, username: 'expired', role: 'user' })
    const auth = authModule.useAuth()

    await expect(auth.logout()).resolves.toBeUndefined()
    expect(auth.authStatus.value).toBe('anonymous')
    expect(auth.currentUser.value).toBeNull()
  })

  it('does not let an older /me response restore a user after logout', async () => {
    let resolveCurrentUser
    api.getCurrentUser.mockReturnValue(new Promise((resolve) => {
      resolveCurrentUser = resolve
    }))
    api.logout.mockResolvedValue({ data: { ok: true } })
    authModule.setAuthenticatedUser({ id: 13, username: 'leaving', role: 'user' })
    const auth = authModule.useAuth()

    const pendingRevalidation = authModule.bootstrapAuth({ force: true })
    await auth.logout()
    resolveCurrentUser({ data: { user: { id: 13, username: 'leaving', role: 'user' } } })
    await pendingRevalidation

    expect(auth.authStatus.value).toBe('anonymous')
    expect(auth.currentUser.value).toBeNull()
  })

  it('broadcasts auth lifecycle events without copying identity or credentials', async () => {
    const channels = []
    class FakeBroadcastChannel {
      constructor(name) {
        this.name = name
        this.listeners = new Set()
        this.postMessage = vi.fn()
        this.close = vi.fn()
        channels.push(this)
      }

      addEventListener(_type, listener) {
        this.listeners.add(listener)
      }

      removeEventListener(_type, listener) {
        this.listeners.delete(listener)
      }
    }
    setBroadcastChannel(FakeBroadcastChannel)
    authModule.startAuthSynchronization()

    api.login.mockResolvedValue({ data: { user: { id: 20, username: 'alpha', role: 'user' } } })
    api.changePassword.mockResolvedValue({ data: { user: { id: 20, username: 'alpha', role: 'user' } } })
    api.logout.mockResolvedValue({ data: { ok: true } })
    const auth = authModule.useAuth()

    await auth.login('alpha', 'secret-password')
    await auth.changePassword('secret-password', 'new-secret-password')
    await auth.logout()

    expect(channels).toHaveLength(1)
    expect(channels[0].name).toBe('ai-job-consultant-auth')
    const messages = channels[0].postMessage.mock.calls.map(([message]) => message)
    expect(messages.map((message) => message.reason)).toEqual(['login', 'change-password', 'logout'])
    expect(JSON.stringify(messages)).not.toContain('alpha')
    expect(JSON.stringify(messages)).not.toContain('secret-password')
  })

  it('revalidates /me for a remote login and replaces a different account', async () => {
    const channels = []
    class FakeBroadcastChannel {
      constructor() {
        this.listener = null
        channels.push(this)
      }

      addEventListener(_type, listener) {
        this.listener = listener
      }

      removeEventListener() {}
      close() {}
      postMessage() {}
      receive(data) {
        this.listener?.({ data })
      }
    }
    setBroadcastChannel(FakeBroadcastChannel)
    authModule.startAuthSynchronization()
    authModule.setAuthenticatedUser({ id: 30, username: 'first-account', role: 'user' })
    api.getCurrentUser.mockResolvedValue({
      data: { user: { id: 31, username: 'second-account', role: 'admin' } }
    })

    channels[0].receive({
      id: 'remote-login',
      reason: 'login',
      type: 'auth-state-changed',
      version: 1,
      user: { id: 999, role: 'super_admin' }
    })

    await vi.waitFor(() => expect(authModule.useAuth().currentUser.value?.id).toBe(31))
    expect(api.getCurrentUser).toHaveBeenCalledTimes(1)
    expect(authModule.useAuth().currentUser.value.role).toBe('admin')
    expect(authModule.useAuth().lastRemoteAuthChange.value).toMatchObject({ reason: 'login' })
  })

  it('uses a credential-free storage fallback and revalidates when the page becomes visible', async () => {
    const storageSet = vi.spyOn(Storage.prototype, 'setItem')
    authModule.startAuthSynchronization()
    api.login.mockResolvedValue({ data: { user: { id: 40, username: 'fallback-user', role: 'user' } } })
    const auth = authModule.useAuth()
    await auth.login('fallback-user', 'fallback-secret')

    const syncWrite = storageSet.mock.calls.find(([key]) => key === 'ai_auth_sync_event')
    expect(syncWrite).toBeTruthy()
    expect(syncWrite[1]).not.toContain('fallback-user')
    expect(syncWrite[1]).not.toContain('fallback-secret')

    api.getCurrentUser.mockResolvedValue({
      data: { user: { id: 41, username: 'visible-user', role: 'user' } }
    })
    window.dispatchEvent(new StorageEvent('storage', {
      key: 'ai_auth_sync_event',
      newValue: JSON.stringify({
        id: 'remote-storage-login',
        reason: 'login',
        type: 'auth-state-changed',
        version: 1
      })
    }))
    await vi.waitFor(() => expect(auth.currentUser.value?.id).toBe(41))

    api.getCurrentUser.mockResolvedValue({
      data: { user: { id: 42, username: 'visible-user-refreshed', role: 'user' } }
    })
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible'
    })
    document.dispatchEvent(new Event('visibilitychange'))

    await vi.waitFor(() => expect(auth.currentUser.value?.id).toBe(42))
    expect(api.getCurrentUser).toHaveBeenCalledTimes(2)
  })
})
