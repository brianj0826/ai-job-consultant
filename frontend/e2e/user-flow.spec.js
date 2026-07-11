import { expect, test } from '@playwright/test'

const accounts = {
  user: { username: 'career-user', password: 'CareerPass123!' },
  mustChange: { username: 'must-change', password: 'Temporary123!' }
}

const resetMock = async (request) => {
  const response = await request.post('/api/__e2e/reset')
  expect(response.ok()).toBe(true)
}

const loginFromPage = async (page, account) => {
  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(account.username)
  await page.getByPlaceholder('请输入密码').fill(account.password)
  await page.getByRole('button', { name: '登录并继续' }).click()
}

test.beforeEach(async ({ request }) => {
  await resetMock(request)
})

test.describe('normal user browser flow', () => {
  test('logs in with {user}, sends an authenticated stream without user_id, and logs out', async ({ page }) => {
    await loginFromPage(page, accounts.user)
    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole('heading', { name: '职业工作台' })).toBeVisible()

    expect(await page.evaluate(() => ({
      id: localStorage.getItem('ai_user_id'),
      username: localStorage.getItem('ai_username')
    }))).toEqual({ id: null, username: null })

    await page.getByRole('button', { name: /岗位精准匹配/ }).click()
    const composer = page.getByRole('textbox', { name: '向职达 AI 提问' })
    await expect(composer).toBeEnabled()

    const prompt = '请给我一条契约联调建议'
    const streamRequestPromise = page.waitForRequest((request) => (
      request.method() === 'POST' && request.url().endsWith('/api/chat/stream')
    ))
    await composer.fill(prompt)
    await page.getByRole('button', { name: '发送消息' }).click()

    const streamRequest = await streamRequestPromise
    expect(await streamRequest.headerValue('x-csrf-token')).toBeTruthy()
    expect(streamRequest.postDataJSON()).toEqual({
      message: prompt,
      session_id: 101,
      client_request_id: expect.any(String)
    })
    expect(streamRequest.postDataJSON()).not.toHaveProperty('user_id')
    await expect(
      page.getByLabel('AI 求职顾问对话').getByText('这是一个用于浏览器验收的流式回复。')
    ).toBeVisible()

    const matchDrawerTitle = page.getByRole('heading', { name: '岗位匹配分析' })
    await expect(matchDrawerTitle).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(matchDrawerTitle).toBeHidden()

    const logoutRequestPromise = page.waitForRequest((request) => (
      request.method() === 'POST' && request.url().endsWith('/api/auth/logout')
    ))
    await page.getByRole('button', { name: '退出' }).click()
    const logoutRequest = await logoutRequestPromise
    expect(await logoutRequest.headerValue('x-csrf-token')).toBeTruthy()
    await expect(page).toHaveURL(/\/login$/)
    expect((await page.request.get('/api/auth/me')).status()).toBe(401)
  })

  test('redirects a normal user away from administrator routes', async ({ page }) => {
    await loginFromPage(page, accounts.user)
    await expect(page.getByRole('heading', { name: '职业工作台' })).toBeVisible()

    await page.goto('/admin')
    await expect(page).toHaveURL(/\/forbidden$/)
    await expect(page.getByTestId('forbidden-page')).toContainText('无权访问此页面')
  })

  test('forces a reset user to change the temporary password before entering the workspace', async ({ page }) => {
    await loginFromPage(page, accounts.mustChange)
    await expect(page).toHaveURL(/\/change-password$/)
    await expect(page.getByTestId('change-password-page')).toContainText('需要先修改密码')

    const changeRequestPromise = page.waitForRequest((request) => (
      request.method() === 'POST' && request.url().endsWith('/api/auth/change-password')
    ))
    await page.getByLabel('当前密码').fill(accounts.mustChange.password)
    await page.getByLabel('新密码', { exact: true }).fill('ChangedPass123!')
    await page.getByLabel('确认新密码').fill('ChangedPass123!')
    await page.getByRole('button', { name: '保存新密码' }).click()

    const changeRequest = await changeRequestPromise
    expect(await changeRequest.headerValue('x-csrf-token')).toBeTruthy()
    expect(changeRequest.postDataJSON()).toEqual({
      current_password: accounts.mustChange.password,
      new_password: 'ChangedPass123!'
    })
    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole('heading', { name: '职业工作台' })).toBeVisible()

    const me = await page.request.get('/api/auth/me')
    expect((await me.json()).user.must_change_password).toBe(false)
  })
})
