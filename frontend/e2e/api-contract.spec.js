import { expect, test } from '@playwright/test'

const credentials = {
  user: { username: 'career-user', password: 'CareerPass123!' },
  mustChange: { username: 'must-change', password: 'Temporary123!' },
  admin: { username: 'team-admin', password: 'AdminPass123!' },
  superAdmin: { username: 'root-admin', password: 'AdminPass123!' }
}

const resetMock = async (request) => {
  const response = await request.post('/api/__e2e/reset')
  expect(response.ok()).toBe(true)
}

const login = async (request, account) => {
  const response = await request.post('/api/auth/login', { data: account })
  expect(response.ok()).toBe(true)
  const payload = await response.json()
  expect(payload.user).toMatchObject({ username: account.username, status: 'active' })
  return payload.user
}

const authCookies = async (request) => {
  const state = await request.storageState()
  const session = state.cookies.find((cookie) => cookie.name === 'session_token')
  const csrf = state.cookies.find((cookie) => cookie.name === 'csrf_token')
  expect(session).toMatchObject({ httpOnly: true, sameSite: 'Lax' })
  expect(csrf).toMatchObject({ httpOnly: false, sameSite: 'Lax' })
  return { csrf: csrf.value, session: session.value }
}

test.beforeEach(async ({ request }) => {
  await resetMock(request)
})

test.describe('authenticated user API contract', () => {
  test('issues {user} and both cookies, restores the session, rotates it on password change, and logs out', async ({ request }) => {
    const user = await login(request, credentials.user)
    expect(user).toMatchObject({
      id: 7,
      role: 'user',
      must_change_password: false
    })

    const firstCookies = await authCookies(request)
    const me = await request.get('/api/auth/me')
    expect(await me.json()).toEqual({ user })

    const missingCsrf = await request.post('/api/auth/change-password', {
      data: { current_password: credentials.user.password, new_password: 'UpdatedPass123!' }
    })
    expect(missingCsrf.status()).toBe(403)
    expect(await missingCsrf.json()).toEqual({ detail: 'CSRF token required' })

    const changed = await request.post('/api/auth/change-password', {
      data: { current_password: credentials.user.password, new_password: 'UpdatedPass123!' },
      headers: { 'X-CSRF-Token': firstCookies.csrf }
    })
    expect(changed.ok()).toBe(true)
    expect((await changed.json()).user.must_change_password).toBe(false)

    const rotatedCookies = await authCookies(request)
    expect(rotatedCookies.session).not.toBe(firstCookies.session)
    expect(rotatedCookies.csrf).not.toBe(firstCookies.csrf)

    const logout = await request.post('/api/auth/logout', {
      headers: { 'X-CSRF-Token': rotatedCookies.csrf }
    })
    expect(logout.ok()).toBe(true)
    expect((await request.get('/api/auth/me')).status()).toBe(401)
  })

  test('requires CSRF for writes and prevents access to another user session', async ({ request }) => {
    await login(request, credentials.user)
    const { csrf } = await authCookies(request)

    const rejectedCreate = await request.post('/api/sessions/', {
      data: { name: '缺少 CSRF 的会话' }
    })
    expect(rejectedCreate.status()).toBe(403)

    const created = await request.post('/api/sessions/', {
      data: { name: '契约测试会话' },
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(created.ok()).toBe(true)
    expect(await created.json()).toEqual({ session_id: expect.any(Number) })

    const foreignHistory = await request.get('/api/sessions/201/messages')
    expect(foreignHistory.status()).toBe(404)
    expect(await foreignHistory.json()).toEqual({ detail: '会话不存在' })

    const foreignStream = await request.post('/api/chat/stream', {
      data: { message: '不能写入其他用户会话', session_id: 201 },
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(foreignStream.status()).toBe(404)

    const stream = await request.post('/api/chat/stream', {
      data: { message: '请给出一个简短建议', session_id: 101 },
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(stream.ok()).toBe(true)
    const events = await stream.text()
    expect(events).toContain('"token"')
    expect(events).toContain('"done":true')
    expect(events).toContain('"msg_id"')
  })

  test('allows session inspection and password change while returning 428 for other forced-change requests', async ({ request }) => {
    const user = await login(request, credentials.mustChange)
    expect(user.must_change_password).toBe(true)
    const { csrf } = await authCookies(request)

    const me = await request.get('/api/auth/me')
    expect(me.ok()).toBe(true)
    expect((await me.json()).user.must_change_password).toBe(true)
    const blocked = await request.get('/api/sessions/')
    expect(blocked.status()).toBe(428)
    expect(await blocked.json()).toEqual({ detail: 'Password change required' })

    const changed = await request.post('/api/auth/change-password', {
      data: {
        current_password: credentials.mustChange.password,
        new_password: 'ChangedPass123!'
      },
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(changed.ok()).toBe(true)
    expect((await changed.json()).user.must_change_password).toBe(false)
    expect((await request.get('/api/sessions/')).ok()).toBe(true)
  })

  test('keeps MCP within the authenticated user and CSRF boundary', async ({ request }) => {
    expect((await request.get('/api/mcp/')).status()).toBe(401)
    await login(request, credentials.user)
    const { csrf } = await authCookies(request)

    const info = await request.get('/api/mcp/')
    expect(info.ok()).toBe(true)
    expect(await info.json()).toMatchObject({ authenticated_user_id: 7 })

    const noCsrf = await request.post('/api/mcp/', {
      data: { jsonrpc: '2.0', id: 1, method: 'tools/list' }
    })
    expect(noCsrf.status()).toBe(403)

    const rpc = await request.post('/api/mcp/', {
      data: { jsonrpc: '2.0', id: 1, method: 'tools/list' },
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(rpc.ok()).toBe(true)
    expect(await rpc.json()).toMatchObject({ jsonrpc: '2.0', id: 1 })
  })

  test('replays a completed client_request_id without duplicating messages and rejects changed content', async ({ request }) => {
    await login(request, credentials.user)
    const { csrf } = await authCookies(request)
    const before = await (await request.get('/api/sessions/101/messages')).json()
    const data = {
      message: '幂等请求内容',
      session_id: 101,
      client_request_id: 'contract-idempotency-1'
    }

    const first = await request.post('/api/chat/stream', {
      data,
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(first.ok()).toBe(true)
    expect(await first.text()).not.toContain('"replayed":true')

    const replay = await request.post('/api/chat/stream', {
      data,
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(replay.ok()).toBe(true)
    expect(await replay.text()).toContain('"replayed":true')
    const after = await (await request.get('/api/sessions/101/messages')).json()
    expect(after).toHaveLength(before.length + 2)

    const mismatch = await request.post('/api/chat/stream', {
      data: { ...data, message: '不同的消息内容' },
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(mismatch.status()).toBe(409)
  })
})

test.describe('administrator API contract', () => {
  test('allows an admin to manage a normal status but not roles or password resets', async ({ request }) => {
    const admin = await login(request, credentials.admin)
    expect(admin.role).toBe('admin')
    const { csrf } = await authCookies(request)
    expect((await request.get('/api/admin/overview')).ok()).toBe(true)

    const disabled = await request.patch('/api/admin/users/7/status', {
      data: { status: 'disabled' },
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(disabled.ok()).toBe(true)
    expect((await disabled.json()).user.status).toBe('disabled')

    const role = await request.patch('/api/admin/users/7/role', {
      data: { role: 'admin' },
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(role.status()).toBe(403)
    const reset = await request.post('/api/admin/users/7/reset-password', {
      headers: { 'X-CSRF-Token': csrf }
    })
    expect(reset.status()).toBe(403)
  })

  test('rejects normal users and lets a super-admin manage users with audit records', async ({ request }) => {
    await login(request, credentials.user)
    expect((await request.get('/api/admin/overview')).status()).toBe(403)

    await resetMock(request)
    const admin = await login(request, credentials.superAdmin)
    expect(admin.role).toBe('super_admin')
    const { csrf } = await authCookies(request)

    const users = await request.get('/api/admin/users?page=1&page_size=20&search=career')
    expect(users.ok()).toBe(true)
    expect(await users.json()).toMatchObject({
      items: [expect.objectContaining({ id: 7, username: 'career-user', role: 'user' })],
      page: 1,
      page_size: 20,
      total: 1
    })

    const noCsrf = await request.patch('/api/admin/users/7/status', {
      data: { status: 'disabled' }
    })
    expect(noCsrf.status()).toBe(403)

    const promoted = await request.patch('/api/admin/users/7/role', {
      data: { role: 'admin' },
      headers: { 'X-CSRF-Token': csrf }
    })
    expect((await promoted.json()).user.role).toBe('admin')

    const reset = await request.post('/api/admin/users/7/reset-password', {
      headers: { 'X-CSRF-Token': csrf }
    })
    const resetPayload = await reset.json()
    expect(resetPayload.user.must_change_password).toBe(true)
    expect(resetPayload.temporary_password.length).toBeGreaterThanOrEqual(8)

    const audit = await request.get('/api/admin/audit-logs')
    const auditPayload = await audit.json()
    expect(auditPayload.items.map((entry) => entry.action)).toEqual(expect.arrayContaining([
      'admin.login',
      'user.role_updated',
      'user.password_reset'
    ]))
  })
})
