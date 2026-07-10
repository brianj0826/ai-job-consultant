import { describe, expect, it, vi } from 'vitest'

const request = vi.hoisted(() => ({
  delete: vi.fn(),
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn()
}))

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => request)
  }
}))

const api = await import('./index.js')

describe('frontend API contract', () => {
  it('sends login credentials to the login endpoint', () => {
    api.login('career-user', 'secret')
    expect(request.post).toHaveBeenCalledWith('/api/users/login', {
      username: 'career-user',
      password: 'secret'
    })
  })

  it('keeps session and analytics requests scoped to the active user', () => {
    api.getSessions(12)
    api.getAnalyticsTrend(12, 14)

    expect(request.get).toHaveBeenCalledWith('/api/sessions/', {
      params: { user_id: 12 }
    })
    expect(request.get).toHaveBeenCalledWith('/api/analytics/trend', {
      params: { user_id: 12, days: 14 }
    })
  })
})
