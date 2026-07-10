import axios from 'axios'

const API_BASE = ''

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000
})

// ================= 用户 =================
export const login = (username, password = '') =>
  api.post('/api/users/login', { username, password })

export const register = (username, password) =>
  api.post('/api/users/register', { username, password })

// ================= 会话 =================
export const getSessions = (userId) =>
  api.get('/api/sessions/', { params: { user_id: userId } })

export const createSession = (userId, name = '新对话') =>
  api.post('/api/sessions/', { user_id: userId, name })

export const deleteSession = (sessionId) =>
  api.delete(`/api/sessions/${sessionId}`)

export const renameSession = (sessionId, name) =>
  api.put(`/api/sessions/${sessionId}/rename`, { name })

export const getMessages = (sessionId) =>
  api.get(`/api/sessions/${sessionId}/messages`)

// ================= 聊天 =================
export const sendMessage = (data) =>
  api.post('/api/chat/', data)

// ================= 文档（新增 user_id） =================
export const uploadPDF = (formData) =>
  api.post('/api/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })

export const getDocStatus = (userId) =>
  api.get('/api/documents/status', { params: { user_id: userId } })

export const deleteSource = (userId, source) =>
  api.delete('/api/documents/source', { data: { user_id: userId, source } })

export const fetchUrlContent = (url) =>
  api.post('/api/documents/fetch-url', { url })

// ================= 反馈 =================
export const submitFeedback = (msgId, feedback) =>
  api.post('/api/feedback/', { msg_id: msgId, feedback })

// ================= 数据分析 =================
export const getAnalyticsOverview = (userId) =>
  api.get('/api/analytics/overview', { params: { user_id: userId } })

export const getAnalyticsFeedback = (userId) =>
  api.get('/api/analytics/feedback', { params: { user_id: userId } })

export const getAnalyticsTrend = (userId, days = 7) =>
  api.get('/api/analytics/trend', { params: { user_id: userId, days } })