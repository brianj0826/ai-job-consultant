import { beforeEach, describe, expect, it, vi } from 'vitest'

const request = vi.hoisted(() => ({
  delete: vi.fn(),
  get: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
  put: vi.fn()
}))
const authenticatedFetch = vi.hoisted(() => vi.fn())

vi.mock('./client', () => ({
  ApiError: class ApiError extends Error {},
  api: request,
  authenticatedFetch,
  getCsrfToken: vi.fn(),
  getErrorMessage: vi.fn()
}))

const api = await import('./index.js')

describe('frontend API contract', () => {
  beforeEach(() => {
    Object.values(request).forEach((mock) => mock.mockReset())
    authenticatedFetch.mockReset()
  })

  it('uses the cookie-backed authentication contract', () => {
    api.login('career-user', 'secret123')
    api.register('new-user', 'secret123')
    api.getCurrentUser()
    api.logout()
    api.changePassword('old-secret', 'new-secret')

    expect(request.post).toHaveBeenCalledWith('/api/auth/login', {
      username: 'career-user', password: 'secret123'
    })
    expect(request.post).toHaveBeenCalledWith('/api/auth/register', {
      username: 'new-user', password: 'secret123'
    })
    expect(request.get).toHaveBeenCalledWith('/api/auth/me')
    expect(request.post).toHaveBeenCalledWith('/api/auth/logout')
    expect(request.post).toHaveBeenCalledWith('/api/auth/change-password', {
      current_password: 'old-secret', new_password: 'new-secret'
    })
  })

  it('does not send user_id as an authorization input', () => {
    api.getSessions()
    api.createSession('目标岗位')
    api.getDocStatus()
    api.deleteSource('resume.pdf')
    api.getAnalyticsOverview()
    api.getAnalyticsTrend(14)

    expect(request.get).toHaveBeenCalledWith('/api/sessions/')
    expect(request.post).toHaveBeenCalledWith('/api/sessions/', { name: '目标岗位' })
    expect(request.get).toHaveBeenCalledWith('/api/documents/status')
    expect(request.delete).toHaveBeenCalledWith('/api/documents/source', {
      data: { source: 'resume.pdf' }
    })
    expect(request.get).toHaveBeenCalledWith('/api/analytics/overview')
    expect(request.get).toHaveBeenCalledWith('/api/analytics/trend', {
      params: { days: 14 }
    })
  })

  it('sends the idempotency key through the authenticated stream client', () => {
    api.streamMessage({
      message: '分析简历',
      session_id: 12,
      client_request_id: 'request-123'
    }, { signal: 'signal' })

    expect(authenticatedFetch).toHaveBeenCalledWith('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: '分析简历',
        session_id: 12,
        client_request_id: 'request-123'
      }),
      signal: 'signal'
    })
  })

  it('keeps super-admin password reset server-generated', () => {
    api.resetAdminUserPassword(9)
    expect(request.post).toHaveBeenCalledWith('/api/admin/users/9/reset-password')
  })

  it('uses the authenticated career workspace contract without user_id', () => {
    api.getCareerResources('resumes', { status: 'active' })
    api.getCareerResource('interviews', 3)
    api.createCareerResource('jobs', { title: '产品经理' })
    api.updateCareerResource('skills', 7, { progress: 60 })
    api.deleteCareerResource('reports', 9)
    api.createInterviewQuestion(3, { question: '请介绍一个项目' })
    api.updateInterviewQuestion(3, 11, { score: 90 })
    api.deleteInterviewQuestion(3, 11)

    expect(request.get).toHaveBeenCalledWith('/api/career/resumes', {
      params: { status: 'active' }
    })
    expect(request.get).toHaveBeenCalledWith('/api/career/interviews/3')
    expect(request.post).toHaveBeenCalledWith('/api/career/jobs', { title: '产品经理' })
    expect(request.patch).toHaveBeenCalledWith('/api/career/skills/7', { progress: 60 })
    expect(request.delete).toHaveBeenCalledWith('/api/career/reports/9')
    expect(request.post).toHaveBeenCalledWith('/api/career/interviews/3/questions', {
      question: '请介绍一个项目'
    })
    expect(request.patch).toHaveBeenCalledWith('/api/career/interviews/3/questions/11', {
      score: 90
    })
    expect(request.delete).toHaveBeenCalledWith('/api/career/interviews/3/questions/11')
  })

  it('requires the server-side confirmation contract when clearing career data', () => {
    api.exportCareerData()
    api.deleteCareerData()

    expect(request.get).toHaveBeenCalledWith('/api/career/export')
    expect(request.delete).toHaveBeenCalledWith('/api/career/data', {
      data: { confirmation: 'DELETE' }
    })
  })
})
