import http from 'node:http'

const port = 8001
const interruptionAttempts = new Map()

const sessions = [{ id: 101, name: '动效回归测试会话' }]
const historyMessages = Array.from({ length: 50 }, (_, index) => ({
  id: index + 1,
  role: index % 2 === 0 ? 'user' : 'assistant',
  content: index % 2 === 0
    ? `第 ${index + 1} 条历史问题`
    : `第 ${index + 1} 条历史回复，用于验证长会话中的渲染与滚动。`,
  feedback: null,
  timestamp: new Date(Date.UTC(2026, 6, 10, 8, index)).toISOString()
}))

const sendJson = (response, status, data) => {
  response.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store'
  })
  response.end(JSON.stringify(data))
}

const readJson = async (request) => {
  let body = ''
  for await (const chunk of request) body += chunk
  if (!body) return {}
  try {
    return JSON.parse(body)
  } catch {
    return {}
  }
}

const streamReply = async (request, response) => {
  const payload = await readJson(request)
  const prompt = String(payload.message || '')
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
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no'
  })
  response.flushHeaders()

  let index = 0
  const timer = setInterval(() => {
    if (response.destroyed) {
      clearInterval(timer)
      return
    }

    if (index < tokens.length) {
      response.write(`data: ${JSON.stringify({ token: tokens[index] })}\n\n`)
      index += 1
      return
    }

    clearInterval(timer)
    if (shouldComplete) {
      response.write(`data: ${JSON.stringify({
        done: true,
        msg_id: Date.now(),
        sources: []
      })}\n\n`)
    }
    response.end()
  }, interval)

  response.on('close', () => clearInterval(timer))
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url || '/', `http://${request.headers.host || `127.0.0.1:${port}`}`)
  const path = url.pathname

  if (request.method === 'GET' && path === '/api/health') {
    sendJson(response, 200, { status: 'healthy' })
    return
  }

  if (request.method === 'POST' && (path === '/api/users/login' || path === '/api/users/register')) {
    sendJson(response, 200, { user_id: 7, message: '登录成功' })
    return
  }

  if (request.method === 'GET' && path === '/api/sessions/') {
    sendJson(response, 200, sessions)
    return
  }

  if (request.method === 'POST' && path === '/api/sessions/') {
    sendJson(response, 200, { session_id: 102 })
    return
  }

  if (request.method === 'GET' && path === '/api/sessions/101/messages') {
    sendJson(response, 200, historyMessages)
    return
  }

  if (request.method === 'GET' && path === '/api/sessions/102/messages') {
    sendJson(response, 200, [])
    return
  }

  if (request.method === 'GET' && path === '/api/documents/status') {
    sendJson(response, 200, { doc_count: 0, sources: [] })
    return
  }

  if (request.method === 'GET' && path === '/api/analytics/overview') {
    sendJson(response, 200, { total_sessions: 1, total_messages: 50, avg_per_session: 50 })
    return
  }

  if (request.method === 'GET' && path === '/api/analytics/feedback') {
    sendJson(response, 200, { likes: 8, dislikes: 1, no_feedback: 41, total_rated: 9, like_rate: 89 })
    return
  }

  if (request.method === 'GET' && path === '/api/analytics/trend') {
    sendJson(response, 200, Array.from({ length: 7 }, (_, index) => ({
      date: `2026-07-${String(index + 4).padStart(2, '0')}`,
      count: index + 2
    })))
    return
  }

  if (request.method === 'POST' && path === '/api/chat/stream') {
    await streamReply(request, response)
    return
  }

  if (request.method === 'POST' && path === '/api/feedback/') {
    sendJson(response, 200, { ok: true })
    return
  }

  sendJson(response, 404, {
    detail: `No E2E mock for ${request.method || 'UNKNOWN'} ${path}`
  })
})

server.listen(port, '127.0.0.1')

const shutdown = () => server.close(() => process.exit(0))
process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
