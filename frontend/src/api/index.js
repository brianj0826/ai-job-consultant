import { api, authenticatedFetch } from './client'

// Authentication
export const login = (username, password) =>
  api.post('/api/auth/login', { username, password })

export const register = (username, password) =>
  api.post('/api/auth/register', { username, password })

export const getCurrentUser = () => api.get('/api/auth/me')

export const logout = () => api.post('/api/auth/logout')

export const changePassword = (currentPassword, newPassword) =>
  api.post('/api/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword
  })

// Sessions
export const getSessions = () => api.get('/api/sessions/')

export const createSession = (name = '新对话') =>
  api.post('/api/sessions/', { name })

export const deleteSession = (sessionId) =>
  api.delete(`/api/sessions/${sessionId}`)

export const renameSession = (sessionId, name) =>
  api.put(`/api/sessions/${sessionId}/rename`, { name })

export const getMessages = (sessionId) =>
  api.get(`/api/sessions/${sessionId}/messages`)

// Chat
export const sendMessage = (data) => api.post('/api/chat/', data)

export const streamMessage = (data, options = {}) => authenticatedFetch('/api/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
  signal: options.signal
})

// Documents
export const uploadPDF = (formData) => api.post('/api/documents/upload', formData)

export const getDocStatus = () => api.get('/api/documents/status')

export const deleteSource = (source) =>
  api.delete('/api/documents/source', { data: { source } })

export const fetchUrlContent = (url) =>
  api.post('/api/documents/fetch-url', { url })

// Structured career workspace
const careerResourcePath = (resource, resourceId = null) => {
  const base = `/api/career/${resource}`
  return resourceId === null || resourceId === undefined ? base : `${base}/${resourceId}`
}

export const getCareerResources = (resource, params = {}) =>
  api.get(careerResourcePath(resource), { params })

export const getCareerResource = (resource, resourceId) =>
  api.get(careerResourcePath(resource, resourceId))

export const createCareerResource = (resource, data) =>
  api.post(careerResourcePath(resource), data)

export const updateCareerResource = (resource, resourceId, data) =>
  api.patch(careerResourcePath(resource, resourceId), data)

export const deleteCareerResource = (resource, resourceId) =>
  api.delete(careerResourcePath(resource, resourceId))

export const createInterviewQuestion = (interviewId, data) =>
  api.post(`/api/career/interviews/${interviewId}/questions`, data)

export const updateInterviewQuestion = (interviewId, questionId, data) =>
  api.patch(`/api/career/interviews/${interviewId}/questions/${questionId}`, data)

export const deleteInterviewQuestion = (interviewId, questionId) =>
  api.delete(`/api/career/interviews/${interviewId}/questions/${questionId}`)

export const exportCareerData = () => api.get('/api/career/export')

export const deleteCareerData = () =>
  api.delete('/api/career/data', { data: { confirmation: 'DELETE' } })

// Feedback
export const submitFeedback = (msgId, feedback) =>
  api.post('/api/feedback/', { msg_id: msgId, feedback })

// User analytics
export const getAnalyticsOverview = () => api.get('/api/analytics/overview')

export const getAnalyticsFeedback = () => api.get('/api/analytics/feedback')

export const getAnalyticsTrend = (days = 7) =>
  api.get('/api/analytics/trend', { params: { days } })

// Health
export const getHealth = async () => {
  try {
    return await api.get('/api/health/ready', { timeout: 5000 })
  } catch (error) {
    if (error.status !== 404) throw error
    return api.get('/api/health', { timeout: 5000 })
  }
}

// Administration
export const getAdminOverview = () => api.get('/api/admin/overview')

export const getAdminUsers = ({ page = 1, pageSize = 20, search = '' } = {}) =>
  api.get('/api/admin/users', {
    params: { page, page_size: pageSize, search: search || undefined }
  })

export const updateAdminUserStatus = (userId, status) =>
  api.patch(`/api/admin/users/${userId}/status`, { status })

export const updateAdminUserRole = (userId, role) =>
  api.patch(`/api/admin/users/${userId}/role`, { role })

export const resetAdminUserPassword = (userId) =>
  api.post(`/api/admin/users/${userId}/reset-password`)

export const getAdminFeedback = ({ page = 1, pageSize = 20, feedback = '' } = {}) =>
  api.get('/api/admin/feedback', {
    params: { page, page_size: pageSize, feedback: feedback || undefined }
  })

export const getAdminAuditLogs = ({ page = 1, pageSize = 20, action = '' } = {}) =>
  api.get('/api/admin/audit-logs', {
    params: { page, page_size: pageSize, action: action || undefined }
  })

export { ApiError, authenticatedFetch, getCsrfToken, getErrorMessage } from './client'
