import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const axiosMock = vi.hoisted(() => {
  const requestUse = vi.fn()
  const responseUse = vi.fn()
  return {
    create: vi.fn(() => ({
      interceptors: {
        request: { use: requestUse },
        response: { use: responseUse }
      }
    })),
    requestUse,
    responseUse
  }
})

vi.mock('axios', () => ({ default: { create: axiosMock.create } }))

const client = await import('./client.js')

describe('authenticated API client', () => {
  beforeEach(() => {
    document.cookie = 'csrf_token=csrf-value; path=/'
  })

  afterEach(() => {
    document.cookie = 'csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
    vi.unstubAllGlobals()
  })

  it('configures cookie credentials and the backend CSRF names', () => {
    expect(axiosMock.create).toHaveBeenCalledWith(expect.objectContaining({
      withCredentials: true,
      xsrfCookieName: 'csrf_token',
      xsrfHeaderName: 'X-CSRF-Token'
    }))
  })

  it('adds CSRF to unsafe axios requests but not reads', () => {
    const requestInterceptor = axiosMock.requestUse.mock.calls[0][0]
    const set = vi.fn()
    requestInterceptor({ method: 'post', headers: { set } })
    expect(set).toHaveBeenCalledWith('X-CSRF-Token', 'csrf-value')

    set.mockClear()
    requestInterceptor({ method: 'get', headers: { set } })
    expect(set).not.toHaveBeenCalled()
  })

  it('uses include credentials and CSRF for authenticated fetch', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetch)
    await client.authenticatedFetch('/api/chat/stream', { method: 'POST' })

    const options = fetch.mock.calls[0][1]
    expect(options.credentials).toBe('include')
    expect(options.headers.get('X-CSRF-Token')).toBe('csrf-value')
  })

  it('maps 428 and invokes the password-change lifecycle hook', async () => {
    const required = vi.fn()
    client.setPasswordChangeRequiredHandler(required)
    const response = new Response(JSON.stringify({ detail: 'Password change required' }), {
      status: 428,
      headers: { 'Content-Type': 'application/json' }
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))

    await expect(client.authenticatedFetch('/api/sessions/', { method: 'POST' }))
      .rejects.toMatchObject({ status: 428 })
    expect(required).toHaveBeenCalledTimes(1)
  })
})
