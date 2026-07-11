import { expect, test } from '@playwright/test'

test('Docker stack connects the Vue UI, FastAPI, MySQL, Redis and mocked AI provider', async ({ page }) => {
  const username = `docker-user-${Date.now()}`
  const password = 'DockerPass123!'

  await page.goto('/login')
  await page.locator('.mode-link').click()
  await page.locator('input[autocomplete="username"]').fill(username)
  const passwordInputs = page.locator('input[autocomplete="new-password"]')
  await passwordInputs.nth(0).fill(password)
  await passwordInputs.nth(1).fill(password)
  await page.locator('.submit-btn').click()

  await expect(page).toHaveURL(/\/$/)
  const composer = page.locator('#chat-message-input')
  await expect(composer).toBeEnabled()

  const streamRequestPromise = page.waitForRequest((request) => (
    request.method() === 'POST' && request.url().endsWith('/api/chat/stream')
  ))
  await composer.fill('Run the Docker integration smoke test')
  await page.getByRole('button', { name: '发送消息' }).click()

  const streamRequest = await streamRequestPromise
  expect(await streamRequest.headerValue('x-csrf-token')).toBeTruthy()
  expect(streamRequest.postDataJSON()).toEqual({
    message: 'Run the Docker integration smoke test',
    session_id: expect.any(Number),
    client_request_id: expect.any(String)
  })
  expect(streamRequest.postDataJSON()).not.toHaveProperty('user_id')
  await expect(
    page.getByLabel('AI 求职顾问对话').getByText('Docker mock reply')
  ).toBeVisible()

  await page.getByRole('button', { name: '退出' }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect((await page.request.get('/api/auth/me')).status()).toBe(401)
})

test('Docker bootstrap super-admin reaches the administrator overview', async ({ page }) => {
  await page.goto('/login')
  await page.locator('input[autocomplete="username"]').fill('root-admin')
  await page.locator('input[autocomplete="current-password"]').fill('AdminPass123!')
  await page.locator('.submit-btn').click()

  await expect(page).toHaveURL(/\/admin\/overview\/?$/)
  await expect(page.getByTestId('admin-overview-page')).toBeVisible()
})
