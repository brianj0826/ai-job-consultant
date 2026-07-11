import axios from 'axios'

const SAFE_METHODS = new Set(['get', 'head', 'options'])
const CSRF_COOKIE_NAME = 'csrf_token'
const CSRF_HEADER_NAME = 'X-CSRF-Token'

let unauthorizedHandler = null
let passwordChangeRequiredHandler = null

export class ApiError extends Error {
  constructor(message, {
    status = 0,
    detail = '',
    retryAfter = null,
    response = null,
    cause = null
  } = {}) {
    super(message, cause ? { cause } : undefined)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.retryAfter = retryAfter
    this.response = response
  }
}

export const setUnauthorizedHandler = (handler) => {
  unauthorizedHandler = typeof handler === 'function' ? handler : null
}

export const setPasswordChangeRequiredHandler = (handler) => {
  passwordChangeRequiredHandler = typeof handler === 'function' ? handler : null
}

export const readCookie = (name) => {
  if (typeof document === 'undefined' || !document.cookie) return ''
  const prefix = `${encodeURIComponent(name)}=`
  const part = document.cookie
    .split(';')
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix))
  if (!part) return ''
  try {
    return decodeURIComponent(part.slice(prefix.length))
  } catch {
    return part.slice(prefix.length)
  }
}

export const getCsrfToken = () => readCookie(CSRF_COOKIE_NAME)

const retryAfterFrom = (headers) => {
  const value = headers?.get?.('retry-after') ?? headers?.['retry-after']
  if (value === undefined || value === null || value === '') return null
  const seconds = Number.parseInt(value, 10)
  return Number.isFinite(seconds) ? seconds : null
}

const userMessageFor = (status, detail, retryAfter) => {
  if (status === 401) return '登录状态已失效，请重新登录。'
  if (status === 403) return detail || '你没有权限执行此操作。'
  if (status === 404) return detail || '请求的内容不存在或已被移除。'
  if (status === 409) return detail || '当前数据已发生变化，请刷新后重试。'
  if (status === 422) return detail || '提交的数据格式不正确，请检查后重试。'
  if (status === 428) return detail || '请先修改密码，再继续使用其他功能。'
  if (status === 429) {
    return retryAfter
      ? `请求过于频繁，请在 ${retryAfter} 秒后重试。`
      : (detail || '请求过于频繁，请稍后重试。')
  }
  if (status >= 500) return '服务暂时不可用，请稍后重试。'
  return detail || '请求失败，请稍后重试。'
}

const notifyLifecycle = (error) => {
  if (error.status === 401) unauthorizedHandler?.(error)
  if (error.status === 428) passwordChangeRequiredHandler?.(error)
}

export const normalizeApiError = (error) => {
  if (error instanceof ApiError) return error
  const response = error?.response || null
  const status = response?.status || 0
  const detailValue = response?.data?.detail
  const detail = typeof detailValue === 'string'
    ? detailValue
    : (detailValue ? JSON.stringify(detailValue) : '')
  const retryAfter = retryAfterFrom(response?.headers)
  const normalized = new ApiError(
    status ? userMessageFor(status, detail, retryAfter) : '无法连接到服务，请检查网络后重试。',
    { status, detail, retryAfter, response, cause: error }
  )
  notifyLifecycle(normalized)
  return normalized
}

export const errorFromResponse = async (response) => {
  let detail = ''
  try {
    const payload = await response.clone().json()
    const rawDetail = payload?.detail
    detail = typeof rawDetail === 'string'
      ? rawDetail
      : (rawDetail ? JSON.stringify(rawDetail) : '')
  } catch {
    // A non-JSON error body is mapped by status below.
  }
  const retryAfter = retryAfterFrom(response.headers)
  const error = new ApiError(userMessageFor(response.status, detail, retryAfter), {
    status: response.status,
    detail,
    retryAfter,
    response
  })
  notifyLifecycle(error)
  return error
}

export const getErrorMessage = (error, fallback = '操作失败，请稍后重试。') => {
  if (error instanceof ApiError) return error.message
  return error?.response?.data?.detail || error?.message || fallback
}

export const api = axios.create({
  baseURL: '',
  timeout: 60000,
  withCredentials: true,
  xsrfCookieName: CSRF_COOKIE_NAME,
  xsrfHeaderName: CSRF_HEADER_NAME
})

api.interceptors.request.use((config) => {
  const method = (config.method || 'get').toLowerCase()
  if (SAFE_METHODS.has(method)) return config
  const token = getCsrfToken()
  if (!token) return config
  if (typeof config.headers?.set === 'function') {
    config.headers.set(CSRF_HEADER_NAME, token)
  } else {
    config.headers = { ...(config.headers || {}), [CSRF_HEADER_NAME]: token }
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(normalizeApiError(error))
)

export const authenticatedFetch = async (url, options = {}) => {
  const method = (options.method || 'GET').toUpperCase()
  const headers = new Headers(options.headers || {})
  if (!SAFE_METHODS.has(method.toLowerCase())) {
    const token = getCsrfToken()
    if (token) headers.set(CSRF_HEADER_NAME, token)
  }

  let response
  try {
    response = await fetch(url, {
      ...options,
      method,
      headers,
      credentials: options.credentials || 'include'
    })
  } catch (error) {
    throw normalizeApiError(error)
  }

  if (!response.ok) throw await errorFromResponse(response)
  return response
}
