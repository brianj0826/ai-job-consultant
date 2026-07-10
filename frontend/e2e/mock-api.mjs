import crypto from 'node:crypto'
import http from 'node:http'

const port = Number.parseInt(process.env.MOCK_API_PORT || '8001', 10)
const host = '127.0.0.1'
const SESSION_COOKIE = 'session_token'
const CSRF_COOKIE = 'csrf_token'
const CSRF_HEADER = 'x-csrf-token'
const jsonHeaders = {
  'Cache-Control': 'no-store',
  'Content-Type': 'application/json; charset=utf-8'
}

const nowIso = () => new Date().toISOString()
const copy = (value) => structuredClone(value)
const token = (prefix) => `${prefix}-${crypto.randomBytes(18).toString('hex')}`
const isPath = (path, expected) => path === expected || path === `${expected}/`

const initialUsers = () => [
  {
    id: 1,
    username: 'root-admin',
    password: 'AdminPass123!',
    role: 'super_admin',
    status: 'active',
    must_change_password: false,
    last_login_at: null,
    created_at: '2026-07-01T08:00:00Z'
  },
  {
    id: 2,
    username: 'team-admin',
    password: 'AdminPass123!',
    role: 'admin',
    status: 'active',
    must_change_password: false,
    last_login_at: null,
    created_at: '2026-07-02T08:00:00Z'
  },
  {
    id: 7,
    username: 'career-user',
    password: 'CareerPass123!',
    role: 'user',
    status: 'active',
    must_change_password: false,
    last_login_at: null,
    created_at: '2026-07-03T08:00:00Z'
  },
  {
    id: 8,
    username: 'must-change',
    password: 'Temporary123!',
    role: 'user',
    status: 'active',
    must_change_password: true,
    last_login_at: null,
    created_at: '2026-07-04T08:00:00Z'
  },
  {
    id: 9,
    username: 'disabled-user',
    password: 'Disabled123!',
    role: 'user',
    status: 'disabled',
    must_change_password: false,
    last_login_at: null,
    created_at: '2026-07-05T08:00:00Z'
  }
]

const initialSessions = () => [
  { id: 101, user_id: 7, name: '动效回归测试会话', created_at: '2026-07-10T08:00:00Z' },
  { id: 201, user_id: 1, name: '管理员私有会话', created_at: '2026-07-10T08:30:00Z' },
  { id: 301, user_id: 2, name: '普通管理员私有会话', created_at: '2026-07-10T09:00:00Z' }
]

const initialMessages = () => {
  const userHistory = Array.from({ length: 50 }, (_, index) => ({
    id: index + 1,
    user_id: 7,
    session_id: 101,
    role: index % 2 === 0 ? 'user' : 'assistant',
    content: index % 2 === 0
      ? `第 ${index + 1} 条历史问题`
      : `第 ${index + 1} 条历史回复，用于验证长会话中的渲染与滚动。`,
    feedback: index === 1 ? 'like' : index === 3 ? 'dislike' : null,
    timestamp: new Date(Date.UTC(2026, 6, 10, 8, index)).toISOString()
  }))
  return [
    ...userHistory,
    {
      id: 201,
      user_id: 1,
      session_id: 201,
      role: 'assistant',
      content: '管理员私有回复',
      feedback: 'like',
      timestamp: '2026-07-10T09:30:00Z'
    }
  ]
}

let users
let conversations
let messages
let documents
let authSessions
let auditLogs
let requestLog
let interruptionAttempts
let idempotentRequests
let nextUserId
let nextSessionId
let nextMessageId
let nextAuditId

const resetState = () => {
  users = initialUsers()
  conversations = initialSessions()
  messages = initialMessages()
  documents = new Map([
    [7, []],
    [1, [{ source: 'admin-notes.pdf', title: 'admin-notes.pdf', type: 'file', chunks: 2 }]],
    [2, []]
  ])
  authSessions = new Map()
  auditLogs = []
  requestLog = []
  interruptionAttempts = new Map()
  idempotentRequests = new Map()
  nextUserId = 10
  nextSessionId = 400
  nextMessageId = 500
  nextAuditId = 1
}

resetState()

const publicUser = (user) => ({
  id: user.id,
  username: user.username,
  role: user.role,
  status: user.status,
  must_change_password: Boolean(user.must_change_password),
  last_login_at: user.last_login_at,
  created_at: user.created_at
})

const parseCookies = (request) => Object.fromEntries(
  String(request.headers.cookie || '')
    .split(';')
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const separator = part.indexOf('=')
      if (separator < 0) return [part, '']
      return [part.slice(0, separator), decodeURIComponent(part.slice(separator + 1))]
    })
)

const sendJson = (response, status, data, headers = {}) => {
  response.writeHead(status, { ...jsonHeaders, ...headers })
  response.end(JSON.stringify(data))
}

const sendError = (response, status, detail, headers = {}) => {
  sendJson(response, status, { detail }, headers)
}

const readBuffer = async (request) => {
  const chunks = []
  for await (const chunk of request) chunks.push(chunk)
  return Buffer.concat(chunks)
}

const readJson = async (request) => {
  const body = (await readBuffer(request)).toString('utf8')
  if (!body) return {}
  try {
    return JSON.parse(body)
  } catch {
    return {}
  }
}

const validatePassword = (value) => {
  if (typeof value !== 'string') return 'Password must be a string'
  if (value.length < 8 || value.length > 128) return 'Password must contain 8-128 characters'
  return ''
}

const validateUsername = (value) => {
  if (typeof value !== 'string') return 'Username must be a string'
  const normalized = value.trim()
  if (normalized.length < 2 || normalized.length > 64) return 'Username must contain 2-64 characters'
  return ''
}

const sessionCookies = (sessionToken, csrfToken) => [
  `${SESSION_COOKIE}=${encodeURIComponent(sessionToken)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800`,
  `${CSRF_COOKIE}=${encodeURIComponent(csrfToken)}; Path=/; SameSite=Lax; Max-Age=604800`
]

const expiredCookies = () => [
  `${SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`,
  `${CSRF_COOKIE}=; Path=/; SameSite=Lax; Max-Age=0`
]

const issueSession = (user) => {
  const sessionToken = token('session')
  const csrfToken = token('csrf')
  authSessions.set(sessionToken, {
    user_id: user.id,
    csrf_token: csrfToken,
    created_at: nowIso()
  })
  return { sessionToken, csrfToken }
}

const revokeUserSessions = (userId) => {
  for (const [sessionToken, session] of authSessions) {
    if (session.user_id === userId) authSessions.delete(sessionToken)
  }
}

const resolveAuth = (request) => {
  const cookies = parseCookies(request)
  const session = authSessions.get(cookies[SESSION_COOKIE])
  if (!session) return null
  const user = users.find((candidate) => candidate.id === session.user_id)
  if (!user || user.status !== 'active') return null
  return { cookies, session, sessionToken: cookies[SESSION_COOKIE], user }
}

const requireAuth = (request, response) => {
  const auth = resolveAuth(request)
  if (!auth) {
    sendError(response, 401, 'Authentication required')
    return null
  }
  return auth
}

const requireReadyAuth = (request, response) => {
  const auth = requireAuth(request, response)
  if (!auth) return null
  if (auth.user.must_change_password) {
    sendError(response, 428, 'Password change required')
    return null
  }
  return auth
}

const requireCsrf = (request, response, auth) => {
  const cookieToken = auth.cookies[CSRF_COOKIE] || ''
  const headerToken = String(request.headers[CSRF_HEADER] || '')
  if (!cookieToken || !headerToken) {
    sendError(response, 403, 'CSRF token required')
    return false
  }
  if (cookieToken !== headerToken || headerToken !== auth.session.csrf_token) {
    sendError(response, 403, 'Invalid CSRF token')
    return false
  }
  return true
}

const requireAdmin = (request, response) => {
  const auth = requireReadyAuth(request, response)
  if (!auth) return null
  if (!['admin', 'super_admin'].includes(auth.user.role)) {
    sendError(response, 403, 'Administrator access required')
    return null
  }
  return auth
}

const requireSuperAdmin = (request, response) => {
  const auth = requireReadyAuth(request, response)
  if (!auth) return null
  if (auth.user.role !== 'super_admin') {
    sendError(response, 403, 'Super-admin access required')
    return null
  }
  return auth
}

const ownedConversation = (sessionId, userId) => conversations.find(
  (conversation) => conversation.id === sessionId && conversation.user_id === userId
)

const recordAudit = (actor, action, targetId, details = {}) => {
  auditLogs.unshift({
    id: nextAuditId++,
    admin_user_id: actor.id,
    admin_username: actor.username,
    action,
    target_type: 'user',
    target_id: String(targetId),
    details,
    ip_address: host,
    user_agent: 'Playwright E2E mock',
    created_at: nowIso()
  })
}

const pageResult = (items, url) => {
  const page = Math.max(1, Number.parseInt(url.searchParams.get('page') || '1', 10))
  const pageSize = Math.min(100, Math.max(1, Number.parseInt(url.searchParams.get('page_size') || '20', 10)))
  const offset = (page - 1) * pageSize
  return {
    items: items.slice(offset, offset + pageSize),
    page,
    page_size: pageSize,
    total: items.length
  }
}

const reserveChatRequest = (userId, sessionId, prompt, rawRequestId) => {
  if (rawRequestId === undefined || rawRequestId === null) return { state: 'new', key: null }
  const requestId = String(rawRequestId).trim()
  if (!requestId || requestId.length > 128) return { state: 'invalid' }
  const key = `${userId}:${sessionId}:${requestId}`
  const existing = idempotentRequests.get(key)
  if (!existing) {
    idempotentRequests.set(key, { prompt, state: 'processing', assistant: null })
    return { state: 'new', key }
  }
  if (existing.prompt !== prompt) return { state: 'mismatch', key }
  if (existing.state === 'processing') return { state: 'processing', key }
  return { state: 'completed', key, assistant: existing.assistant }
}

const rejectChatReservation = (response, reservation) => {
  if (reservation.state === 'invalid') {
    sendError(response, 400, 'client_request_id 不能为空且不能超过 128 个字符')
    return true
  }
  if (reservation.state === 'mismatch') {
    sendError(response, 409, 'client_request_id 已用于不同的消息内容')
    return true
  }
  if (reservation.state === 'processing') {
    sendError(response, 409, '相同请求正在处理中', { 'Retry-After': '2' })
    return true
  }
  return false
}

const streamReply = async (request, response, auth) => {
  const payload = await readJson(request)
  const sessionId = Number(payload.session_id)
  if (!ownedConversation(sessionId, auth.user.id)) {
    sendError(response, 404, '会话不存在')
    return
  }

  const prompt = String(payload.message || '').trim()
  if (!prompt) {
    sendError(response, 400, '消息内容不能为空。')
    return
  }

  const reservation = reserveChatRequest(
    auth.user.id,
    sessionId,
    prompt,
    payload.client_request_id
  )
  if (rejectChatReservation(response, reservation)) return
  if (reservation.state === 'completed') {
    response.writeHead(200, {
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'Content-Type': 'text/event-stream; charset=utf-8',
      'X-Accel-Buffering': 'no'
    })
    response.write(`data: ${JSON.stringify({ token: reservation.assistant.content })}\n\n`)
    response.end(`data: ${JSON.stringify({
      done: true,
      msg_id: reservation.assistant.id,
      sources: [],
      replayed: true
    })}\n\n`)
    return
  }

  messages.push({
    id: nextMessageId++,
    user_id: auth.user.id,
    session_id: sessionId,
    role: 'user',
    content: prompt,
    feedback: null,
    timestamp: nowIso()
  })

  const isPerformanceRun = prompt.includes('性能流')
  const isInterruptedRun = prompt.includes('中断')
  const attempt = (interruptionAttempts.get(prompt) || 0) + 1
  interruptionAttempts.set(prompt, attempt)

  let tokens
  let interval
  let shouldComplete = true
  if (isPerformanceRun) {
    tokens = Array.from({ length: 1000 }, (_, index) => index % 25 === 24 ? '。' : '流')
    interval = 10
  } else if (isInterruptedRun && attempt === 1) {
    tokens = Array.from('这段已经生成的内容必须在连接中断后保留。')
    interval = 18
    shouldComplete = false
  } else if (isInterruptedRun) {
    tokens = Array.from('重试后的完整回复已生成。')
    interval = 15
  } else {
    tokens = Array.from('这是一个用于浏览器验收的流式回复。')
    interval = 12
  }

  response.writeHead(200, {
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'Content-Type': 'text/event-stream; charset=utf-8',
    'X-Accel-Buffering': 'no'
  })
  response.flushHeaders()

  let index = 0
  let fullText = ''
  const timer = setInterval(() => {
    if (response.destroyed) {
      clearInterval(timer)
      return
    }
    if (index < tokens.length) {
      fullText += tokens[index]
      response.write(`data: ${JSON.stringify({ token: tokens[index] })}\n\n`)
      index += 1
      return
    }

    clearInterval(timer)
    if (shouldComplete) {
      const assistantMessage = {
        id: nextMessageId++,
        user_id: auth.user.id,
        session_id: sessionId,
        role: 'assistant',
        content: fullText,
        feedback: null,
        timestamp: nowIso()
      }
      messages.push(assistantMessage)
      if (reservation.key) {
        idempotentRequests.set(reservation.key, {
          prompt,
          state: 'completed',
          assistant: assistantMessage
        })
      }
      response.write(`data: ${JSON.stringify({
        done: true,
        msg_id: assistantMessage.id,
        sources: []
      })}\n\n`)
    } else if (reservation.key) idempotentRequests.delete(reservation.key)
    response.end()
  }, interval)

  response.on('close', () => clearInterval(timer))
}

const handleAuth = async (request, response, path) => {
  if (request.method === 'POST' && ['/api/auth/register', '/api/users/register'].includes(path)) {
    const payload = await readJson(request)
    const usernameError = validateUsername(payload.username)
    const passwordError = validatePassword(payload.password)
    if (usernameError || passwordError) {
      sendError(response, 400, usernameError || passwordError)
      return true
    }
    const username = payload.username.trim()
    if (users.some((user) => user.username.toLowerCase() === username.toLowerCase())) {
      sendError(response, 409, 'Username is already in use')
      return true
    }
    const user = {
      id: nextUserId++,
      username,
      password: payload.password,
      role: 'user',
      status: 'active',
      must_change_password: false,
      last_login_at: nowIso(),
      created_at: nowIso()
    }
    users.push(user)
    documents.set(user.id, [])
    const credentials = issueSession(user)
    sendJson(response, 201, { user: publicUser(user) }, {
      'Set-Cookie': sessionCookies(credentials.sessionToken, credentials.csrfToken)
    })
    return true
  }

  if (request.method === 'POST' && ['/api/auth/login', '/api/users/login'].includes(path)) {
    const payload = await readJson(request)
    const usernameError = validateUsername(payload.username)
    const passwordError = validatePassword(payload.password)
    if (usernameError || passwordError) {
      sendError(response, 400, usernameError || passwordError)
      return true
    }
    const user = users.find((candidate) => candidate.username === payload.username.trim())
    if (!user || user.password !== payload.password || user.status !== 'active') {
      sendError(response, 401, 'Invalid username or password')
      return true
    }
    user.last_login_at = nowIso()
    const credentials = issueSession(user)
    if (['admin', 'super_admin'].includes(user.role)) {
      recordAudit(user, 'admin.login', user.id, { username: user.username, role: user.role })
    }
    sendJson(response, 200, { user: publicUser(user) }, {
      'Set-Cookie': sessionCookies(credentials.sessionToken, credentials.csrfToken)
    })
    return true
  }

  if (request.method === 'GET' && path === '/api/auth/me') {
    const auth = requireAuth(request, response)
    if (auth) sendJson(response, 200, { user: publicUser(auth.user) })
    return true
  }

  if (request.method === 'POST' && path === '/api/auth/logout') {
    const auth = requireAuth(request, response)
    if (!auth || !requireCsrf(request, response, auth)) return true
    if (['admin', 'super_admin'].includes(auth.user.role)) {
      recordAudit(auth.user, 'admin.logout', auth.user.id, {
        username: auth.user.username,
        role: auth.user.role
      })
    }
    authSessions.delete(auth.sessionToken)
    sendJson(response, 200, { ok: true }, { 'Set-Cookie': expiredCookies() })
    return true
  }

  if (request.method === 'POST' && path === '/api/auth/change-password') {
    const auth = requireAuth(request, response)
    if (!auth || !requireCsrf(request, response, auth)) return true
    const payload = await readJson(request)
    if (payload.current_password !== auth.user.password) {
      sendError(response, 400, 'Current password is incorrect')
      return true
    }
    const passwordError = validatePassword(payload.new_password)
    if (passwordError) {
      sendError(response, 400, passwordError)
      return true
    }
    auth.user.password = payload.new_password
    auth.user.must_change_password = false
    revokeUserSessions(auth.user.id)
    const credentials = issueSession(auth.user)
    sendJson(response, 200, { user: publicUser(auth.user) }, {
      'Set-Cookie': sessionCookies(credentials.sessionToken, credentials.csrfToken)
    })
    return true
  }

  return false
}

const handleSessions = async (request, response, path, auth) => {
  if (request.method === 'GET' && isPath(path, '/api/sessions')) {
    sendJson(response, 200, conversations
      .filter((conversation) => conversation.user_id === auth.user.id)
      .map(({ user_id: _userId, ...conversation }) => conversation))
    return true
  }

  if (request.method === 'POST' && isPath(path, '/api/sessions')) {
    if (!requireCsrf(request, response, auth)) return true
    const payload = await readJson(request)
    const name = String(payload.name || '新对话').trim()
    if (!name || name.length > 255) {
      sendError(response, 400, !name ? '会话名称不能为空' : '会话名称不能超过 255 个字符')
      return true
    }
    const conversation = {
      id: nextSessionId++,
      user_id: auth.user.id,
      name,
      created_at: nowIso()
    }
    conversations.push(conversation)
    sendJson(response, 200, { session_id: conversation.id })
    return true
  }

  const messageMatch = path.match(/^\/api\/sessions\/(\d+)\/messages$/)
  if (request.method === 'GET' && messageMatch) {
    const sessionId = Number(messageMatch[1])
    if (!ownedConversation(sessionId, auth.user.id)) {
      sendError(response, 404, '会话不存在')
      return true
    }
    sendJson(response, 200, messages
      .filter((message) => message.session_id === sessionId && message.user_id === auth.user.id)
      .map(({ user_id: _userId, session_id: _sessionId, ...message }) => message))
    return true
  }

  const renameMatch = path.match(/^\/api\/sessions\/(\d+)\/rename$/)
  if (request.method === 'PUT' && renameMatch) {
    if (!requireCsrf(request, response, auth)) return true
    const conversation = ownedConversation(Number(renameMatch[1]), auth.user.id)
    if (!conversation) {
      sendError(response, 404, '会话不存在')
      return true
    }
    const payload = await readJson(request)
    const name = String(payload.name || '').trim()
    if (!name) {
      sendError(response, 400, '名称不能为空')
      return true
    }
    conversation.name = name
    sendJson(response, 200, { ok: true, name })
    return true
  }

  const deleteMatch = path.match(/^\/api\/sessions\/(\d+)$/)
  if (request.method === 'DELETE' && deleteMatch) {
    if (!requireCsrf(request, response, auth)) return true
    const sessionId = Number(deleteMatch[1])
    if (!ownedConversation(sessionId, auth.user.id)) {
      sendError(response, 404, '会话不存在')
      return true
    }
    conversations = conversations.filter((conversation) => conversation.id !== sessionId)
    messages = messages.filter((message) => message.session_id !== sessionId)
    sendJson(response, 200, { ok: true })
    return true
  }

  return false
}

const handleDocuments = async (request, response, path, auth) => {
  if (request.method === 'GET' && path === '/api/documents/status') {
    const sources = documents.get(auth.user.id) || []
    sendJson(response, 200, {
      doc_count: sources.reduce((total, source) => total + (source.chunks || 1), 0),
      sources: sources.map(({ chunks: _chunks, ...source }) => source)
    })
    return true
  }

  if (request.method === 'POST' && path === '/api/documents/upload') {
    if (!requireCsrf(request, response, auth)) return true
    const body = (await readBuffer(request)).toString('utf8')
    const filename = body.match(/filename="([^"]+)"/i)?.[1] || 'resume.pdf'
    const sources = documents.get(auth.user.id) || []
    if (!sources.some((source) => source.source === filename)) {
      sources.push({ source: filename, title: filename, type: 'file', chunks: 3 })
    }
    documents.set(auth.user.id, sources)
    sendJson(response, 200, { message: `文档 ${filename} 已成功导入知识库` })
    return true
  }

  if (request.method === 'POST' && path === '/api/documents/fetch-url') {
    const payload = await readJson(request)
    sendJson(response, 200, {
      title: 'Mock 招聘页面',
      text: `从 ${String(payload.url || '')} 抓取的职位描述`
    })
    return true
  }

  if (request.method === 'POST' && path === '/api/documents/import-url') {
    if (!requireCsrf(request, response, auth)) return true
    const payload = await readJson(request)
    const sources = documents.get(auth.user.id) || []
    const source = String(payload.url || '').trim()
    sources.push({ source, title: 'Mock 招聘页面', type: 'web', chunks: 2 })
    documents.set(auth.user.id, sources)
    sendJson(response, 200, { message: '已导入 Mock 招聘页面', title: 'Mock 招聘页面', chunks: 2 })
    return true
  }

  if (request.method === 'DELETE' && path === '/api/documents/source') {
    if (!requireCsrf(request, response, auth)) return true
    const payload = await readJson(request)
    const source = String(payload.source || '').trim()
    if (!source) {
      sendError(response, 400, '来源不能为空')
      return true
    }
    documents.set(
      auth.user.id,
      (documents.get(auth.user.id) || []).filter((document) => document.source !== source)
    )
    sendJson(response, 200, { message: `已删除来源 ${source}`, ok: true })
    return true
  }

  return false
}

const handleAnalytics = (request, response, path, auth, url) => {
  const userSessions = conversations.filter((conversation) => conversation.user_id === auth.user.id)
  const userMessages = messages.filter((message) => message.user_id === auth.user.id)
  if (request.method === 'GET' && path === '/api/analytics/overview') {
    sendJson(response, 200, {
      total_sessions: userSessions.length,
      total_messages: userMessages.length,
      avg_per_session: userSessions.length ? Number((userMessages.length / userSessions.length).toFixed(1)) : 0
    })
    return true
  }
  if (request.method === 'GET' && path === '/api/analytics/feedback') {
    const likes = userMessages.filter((message) => message.feedback === 'like').length
    const dislikes = userMessages.filter((message) => message.feedback === 'dislike').length
    const totalRated = likes + dislikes
    sendJson(response, 200, {
      likes,
      dislikes,
      no_feedback: userMessages.length - totalRated,
      total_rated: totalRated,
      like_rate: totalRated ? Math.round((likes / totalRated) * 100) : 0
    })
    return true
  }
  if (request.method === 'GET' && path === '/api/analytics/trend') {
    const days = Math.min(30, Math.max(1, Number.parseInt(url.searchParams.get('days') || '7', 10)))
    sendJson(response, 200, Array.from({ length: days }, (_, index) => ({
      date: `2026-07-${String(index + 1).padStart(2, '0')}`,
      count: index + 2
    })))
    return true
  }
  return false
}

const handleAdmin = async (request, response, path, url) => {
  if (!path.startsWith('/api/admin/')) return false
  const auth = requireAdmin(request, response)
  if (!auth) return true

  if (request.method === 'GET' && path === '/api/admin/overview') {
    const activeUsers = users.filter((user) => user.status === 'active').length
    const rated = messages.filter((message) => message.feedback).length
    sendJson(response, 200, {
      users: {
        total: users.length,
        active: activeUsers,
        administrators: users.filter((user) => ['admin', 'super_admin'].includes(user.role)).length,
        new_today: 0,
        logins_today: users.filter((user) => user.last_login_at).length
      },
      conversations: { total: conversations.length },
      messages: { total: messages.length },
      feedback: {
        likes: messages.filter((message) => message.feedback === 'like').length,
        dislikes: messages.filter((message) => message.feedback === 'dislike').length,
        rated
      },
      auth_sessions: { active: authSessions.size }
    })
    return true
  }

  if (request.method === 'GET' && path === '/api/admin/users') {
    const search = String(url.searchParams.get('search') || '').trim().toLowerCase()
    const items = users
      .filter((user) => !search || user.username.toLowerCase().includes(search))
      .sort((left, right) => right.id - left.id)
      .map((user) => ({
        ...publicUser(user),
        session_count: conversations.filter((conversation) => conversation.user_id === user.id).length,
        message_count: messages.filter((message) => message.user_id === user.id).length
      }))
    sendJson(response, 200, pageResult(items, url))
    return true
  }

  if (request.method === 'GET' && path === '/api/admin/feedback') {
    const feedbackFilter = url.searchParams.get('feedback')
    if (feedbackFilter && !['like', 'dislike'].includes(feedbackFilter)) {
      sendError(response, 400, 'invalid feedback')
      return true
    }
    const items = messages
      .filter((message) => message.role === 'assistant' && message.feedback)
      .filter((message) => !feedbackFilter || message.feedback === feedbackFilter)
      .sort((left, right) => right.id - left.id)
      .map((message) => ({
        id: message.id,
        user_id: message.user_id,
        username: users.find((user) => user.id === message.user_id)?.username || null,
        session_id: message.session_id,
        feedback: message.feedback,
        content: message.content.slice(0, 2000),
        timestamp: message.timestamp
      }))
    sendJson(response, 200, pageResult(items, url))
    return true
  }

  if (request.method === 'GET' && path === '/api/admin/audit-logs') {
    const action = String(url.searchParams.get('action') || '').trim()
    sendJson(response, 200, pageResult(
      auditLogs.filter((entry) => !action || entry.action === action),
      url
    ))
    return true
  }

  const statusMatch = path.match(/^\/api\/admin\/users\/(\d+)\/status$/)
  if (request.method === 'PATCH' && statusMatch) {
    if (!requireCsrf(request, response, auth)) return true
    const target = users.find((user) => user.id === Number(statusMatch[1]))
    if (!target) {
      sendError(response, 404, 'User not found')
      return true
    }
    const payload = await readJson(request)
    if (!['active', 'disabled'].includes(payload.status)) {
      sendError(response, 400, 'invalid status')
      return true
    }
    if (target.id === auth.user.id && target.status !== payload.status) {
      sendError(response, 400, 'You cannot change your own account status')
      return true
    }
    if (target.role !== 'user' && auth.user.role !== 'super_admin') {
      sendError(response, 403, 'Only a super-admin can change a privileged account')
      return true
    }
    const previousStatus = target.status
    target.status = payload.status
    if (payload.status === 'disabled') revokeUserSessions(target.id)
    recordAudit(auth.user, 'user.status_updated', target.id, {
      username: target.username,
      previous_status: previousStatus,
      new_status: target.status
    })
    sendJson(response, 200, { user: publicUser(target) })
    return true
  }

  const roleMatch = path.match(/^\/api\/admin\/users\/(\d+)\/role$/)
  if (request.method === 'PATCH' && roleMatch) {
    if (auth.user.role !== 'super_admin') {
      sendError(response, 403, 'Only a super-admin can assign roles')
      return true
    }
    if (!requireCsrf(request, response, auth)) return true
    const target = users.find((user) => user.id === Number(roleMatch[1]))
    if (!target) {
      sendError(response, 404, 'User not found')
      return true
    }
    const payload = await readJson(request)
    if (!['user', 'admin', 'super_admin'].includes(payload.role)) {
      sendError(response, 400, 'invalid role')
      return true
    }
    if (target.id === auth.user.id && target.role !== payload.role) {
      sendError(response, 400, 'You cannot change your own role')
      return true
    }
    const previousRole = target.role
    target.role = payload.role
    recordAudit(auth.user, 'user.role_updated', target.id, {
      username: target.username,
      previous_role: previousRole,
      new_role: target.role
    })
    sendJson(response, 200, { user: publicUser(target) })
    return true
  }

  const resetMatch = path.match(/^\/api\/admin\/users\/(\d+)\/reset-password$/)
  if (request.method === 'POST' && resetMatch) {
    if (auth.user.role !== 'super_admin') {
      sendError(response, 403, 'Super-admin access required')
      return true
    }
    if (!requireCsrf(request, response, auth)) return true
    const target = users.find((user) => user.id === Number(resetMatch[1]))
    if (!target) {
      sendError(response, 404, 'User not found')
      return true
    }
    if (target.id === auth.user.id) {
      sendError(response, 400, 'You cannot reset your own password')
      return true
    }
    // The real endpoint generates a one-time password server-side so the
    // administrator never chooses or reuses a user's credential.
    const temporaryPassword = crypto.randomBytes(15).toString('base64url')
    target.password = temporaryPassword
    target.must_change_password = true
    revokeUserSessions(target.id)
    recordAudit(auth.user, 'user.password_reset', target.id, { username: target.username })
    sendJson(response, 200, {
      user: publicUser(target),
      temporary_password: temporaryPassword
    })
    return true
  }

  sendError(response, 404, `No E2E mock for ${request.method || 'UNKNOWN'} ${path}`)
  return true
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url || '/', `http://${request.headers.host || `${host}:${port}`}`)
  const path = url.pathname

  if (request.method === 'POST' && path === '/api/__e2e/reset') {
    resetState()
    sendJson(response, 200, { ok: true })
    return
  }
  if (request.method === 'GET' && path === '/api/__e2e/state') {
    sendJson(response, 200, {
      auth_session_count: authSessions.size,
      requests: requestLog,
      users: users.map(publicUser)
    })
    return
  }
  if (request.method === 'GET' && path === '/api/health/live') {
    sendJson(response, 200, { status: 'alive' })
    return
  }
  if (request.method === 'GET' && ['/api/health', '/api/health/ready'].includes(path)) {
    sendJson(response, 200, { status: 'ready', database: 'mock' })
    return
  }

  if (await handleAuth(request, response, path)) return
  if (await handleAdmin(request, response, path, url)) return

  const auth = requireReadyAuth(request, response)
  if (!auth) return
  requestLog.push({ method: request.method, path, user_id: auth.user.id })

  if (await handleSessions(request, response, path, auth)) return
  if (await handleDocuments(request, response, path, auth)) return
  if (handleAnalytics(request, response, path, auth, url)) return

  if (request.method === 'POST' && isPath(path, '/api/chat/stream')) {
    if (!requireCsrf(request, response, auth)) return
    await streamReply(request, response, auth)
    return
  }

  if (request.method === 'POST' && isPath(path, '/api/chat')) {
    if (!requireCsrf(request, response, auth)) return
    const payload = await readJson(request)
    const sessionId = Number(payload.session_id)
    if (!ownedConversation(sessionId, auth.user.id)) {
      sendError(response, 404, '会话不存在')
      return
    }
    const prompt = String(payload.message || '').trim()
    if (!prompt) {
      sendError(response, 400, '消息内容不能为空。')
      return
    }
    const reservation = reserveChatRequest(
      auth.user.id,
      sessionId,
      prompt,
      payload.client_request_id
    )
    if (rejectChatReservation(response, reservation)) return
    if (reservation.state === 'completed') {
      sendJson(response, 200, {
        response: reservation.assistant.content,
        msg_id: reservation.assistant.id,
        sources: [],
        replayed: true
      })
      return
    }
    messages.push({
      id: nextMessageId++,
      user_id: auth.user.id,
      session_id: sessionId,
      role: 'user',
      content: prompt,
      feedback: null,
      timestamp: nowIso()
    })
    const assistantMessage = {
      id: nextMessageId++,
      user_id: auth.user.id,
      session_id: sessionId,
      role: 'assistant',
      content: `Mock 回复：${prompt}`,
      feedback: null,
      timestamp: nowIso()
    }
    messages.push(assistantMessage)
    if (reservation.key) {
      idempotentRequests.set(reservation.key, {
        prompt,
        state: 'completed',
        assistant: assistantMessage
      })
    }
    sendJson(response, 200, {
      response: assistantMessage.content,
      msg_id: assistantMessage.id,
      sources: []
    })
    return
  }

  if (request.method === 'POST' && isPath(path, '/api/feedback')) {
    if (!requireCsrf(request, response, auth)) return
    const payload = await readJson(request)
    const message = messages.find(
      (candidate) => candidate.id === Number(payload.msg_id) && candidate.user_id === auth.user.id
    )
    if (!message) {
      sendError(response, 404, '消息不存在')
      return
    }
    if (message.role !== 'assistant') {
      sendError(response, 400, '只能评价 AI 回复')
      return
    }
    if (!['like', 'dislike'].includes(payload.feedback)) {
      sendError(response, 422, 'Input should be like or dislike')
      return
    }
    message.feedback = payload.feedback
    sendJson(response, 200, { ok: true })
    return
  }

  if (request.method === 'GET' && isPath(path, '/api/mcp')) {
    sendJson(response, 200, {
      name: '职达 MCP',
      protocol: 'JSON-RPC 2.0',
      authenticated_user_id: auth.user.id
    })
    return
  }
  if (request.method === 'POST' && isPath(path, '/api/mcp')) {
    if (!requireCsrf(request, response, auth)) return
    const payload = await readJson(request)
    sendJson(response, 200, {
      jsonrpc: '2.0',
      id: payload.id ?? null,
      result: { ok: true }
    })
    return
  }

  sendError(response, 404, `No E2E mock for ${request.method || 'UNKNOWN'} ${path}`)
})

server.listen(port, host)

const shutdown = () => server.close(() => process.exit(0))
process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
