import { expect, test } from '@playwright/test'

const superAdmin = { username: 'root-admin', password: 'AdminPass123!' }

const resetMock = async (request) => {
  const response = await request.post('/api/__e2e/reset')
  expect(response.ok()).toBe(true)
}

const loginAsSuperAdmin = async (page) => {
  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(superAdmin.username)
  await page.getByPlaceholder('请输入密码').fill(superAdmin.password)
  await page.getByRole('button', { name: '登录并继续' }).click()
  await expect(page).toHaveURL(/\/admin\/overview\/?$/)
  await expect(page.getByTestId('admin-overview-page')).toBeVisible()
}

test.beforeEach(async ({ request }) => {
  await resetMock(request)
})

test('super-admin reviews metrics, manages a user, resets a password, and sees the audit trail', async ({ page }) => {
  await loginAsSuperAdmin(page)
  await expect(page.getByText('用户总数')).toBeVisible()
  await expect(page.getByText('有效认证会话')).toBeVisible()

  await page.getByRole('link', { name: '用户管理' }).click()
  await expect(page.getByTestId('admin-users-page')).toBeVisible()
  await page.getByLabel('按用户名搜索').fill('career-user')
  await page.getByRole('button', { name: '搜索' }).click()

  const row = page.getByRole('row').filter({ hasText: 'career-user' })
  await expect(row).toBeVisible()

  const roleRequestPromise = page.waitForRequest((request) => (
    request.method() === 'PATCH' && request.url().endsWith('/api/admin/users/7/role')
  ))
  await row.locator('.el-select').click()
  await page.getByRole('option', { name: '管理员', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: '确认修改' }).click()
  const roleRequest = await roleRequestPromise
  expect(await roleRequest.headerValue('x-csrf-token')).toBeTruthy()
  expect(roleRequest.postDataJSON()).toEqual({ role: 'admin' })
  await expect(row).toContainText('管理员')

  const resetRequestPromise = page.waitForRequest((request) => (
    request.method() === 'POST' && request.url().endsWith('/api/admin/users/7/reset-password')
  ))
  await row.getByRole('button', { name: '重置密码' }).click()
  await page.getByRole('dialog').getByRole('button', { name: '生成临时密码' }).click()
  const resetRequest = await resetRequestPromise
  expect(await resetRequest.headerValue('x-csrf-token')).toBeTruthy()
  expect(resetRequest.postData()).toBeFalsy()

  const passwordDialog = page.getByRole('dialog', { name: '临时密码（仅显示一次）' })
  const temporaryPassword = (await passwordDialog.locator('.el-message-box__message').innerText()).trim()
  expect(temporaryPassword.length).toBeGreaterThanOrEqual(8)
  await passwordDialog.getByRole('button', { name: '我已安全保存' }).click()

  await page.getByRole('link', { name: '反馈审阅' }).click()
  await expect(page.getByTestId('admin-feedback-page')).toContainText('有帮助')
  await expect(page.getByTestId('admin-feedback-page')).toContainText('需改进')

  await page.getByRole('link', { name: '审计日志' }).click()
  await expect(page.getByTestId('admin-audit-page')).toContainText('user.role_updated')
  await expect(page.getByTestId('admin-audit-page')).toContainText('user.password_reset')
})
