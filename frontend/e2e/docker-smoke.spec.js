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
  await expect(page.getByRole('heading', { name: '职业工作台' })).toBeVisible()

  const cookies = await page.context().cookies()
  const csrfToken = cookies.find((cookie) => cookie.name === 'csrf_token')?.value
  expect(csrfToken).toBeTruthy()
  const write = (data) => ({
    data,
    headers: { 'X-CSRF-Token': csrfToken }
  })

  const resumeResponse = await page.request.post('/api/career/resumes', write({
    title: '全栈候选人简历',
    content: 'Python, Vue, MySQL',
    is_primary: true
  }))
  expect(resumeResponse.status()).toBe(201)

  const jobResponse = await page.request.post('/api/career/jobs', write({
    title: 'AI 产品工程师',
    company: '测试公司',
    description: '负责 AI 产品与工程交付'
  }))
  expect(jobResponse.status()).toBe(201)
  const job = await jobResponse.json()

  const applicationResponse = await page.request.post('/api/career/applications', write({
    job_id: job.id,
    stage: 'applied'
  }))
  expect(applicationResponse.status()).toBe(201)
  const application = await applicationResponse.json()

  const interviewResponse = await page.request.post('/api/career/interviews', write({
    job_id: job.id,
    title: 'Docker 全栈面试',
    status: 'planned'
  }))
  expect(interviewResponse.status()).toBe(201)
  const interview = await interviewResponse.json()

  const questionResponse = await page.request.post(
    `/api/career/interviews/${interview.id}/questions`,
    write({ question: '请介绍一个系统设计取舍', score: 88 })
  )
  expect(questionResponse.status()).toBe(201)

  const reportResponse = await page.request.post('/api/career/reports', write({
    kind: 'job_match',
    title: 'Docker 岗位匹配',
    entity_type: 'job',
    entity_id: job.id,
    summary: '用于验证持久化报告',
    payload: { version: 1, score: 88 }
  }))
  expect(reportResponse.status()).toBe(201)

  const skillResponse = await page.request.post('/api/career/skills', write({
    skill: 'System Design',
    progress: 40
  }))
  expect(skillResponse.status()).toBe(201)

  const deleteJobResponse = await page.request.delete(
    `/api/career/jobs/${job.id}`,
    write(undefined)
  )
  expect(deleteJobResponse.status()).toBe(200)
  expect((await page.request.get(`/api/career/applications/${application.id}`)).status()).toBe(404)
  const preservedInterview = await page.request.get(`/api/career/interviews/${interview.id}`)
  expect(preservedInterview.status()).toBe(200)
  expect((await preservedInterview.json()).job_id).toBeNull()

  const exportResponse = await page.request.get('/api/career/export')
  expect(exportResponse.status()).toBe(200)
  const careerExport = await exportResponse.json()
  expect(careerExport.resumes).toHaveLength(1)
  expect(careerExport.jobs).toHaveLength(0)
  expect(careerExport.applications).toHaveLength(0)
  expect(careerExport.interviews[0].questions).toHaveLength(1)
  expect(careerExport.reports).toHaveLength(1)
  expect(careerExport.skills).toHaveLength(1)

  await page.goto('/interviews')
  await expect(page.getByRole('heading', { name: '面试中心', exact: true }).first()).toBeVisible()
  await expect(page.getByText('Docker 全栈面试').first()).toBeVisible()

  await page.goto('/')
  await page.getByRole('button', { name: /继续职业对话/ }).click()
  const composer = page.getByRole('textbox', { name: '向职达 AI 提问' })
  await expect(composer).toBeEnabled()

  const streamRequestPromise = page.waitForRequest((request) => (
    request.method() === 'POST' && request.url().endsWith('/api/chat/stream')
  ))
  await composer.fill('Please save a Redis skill plan from this Docker integration test')
  await page.getByRole('button', { name: '发送消息' }).click()

  const streamRequest = await streamRequestPromise
  expect(await streamRequest.headerValue('x-csrf-token')).toBeTruthy()
  expect(streamRequest.postDataJSON()).toEqual({
    message: 'Please save a Redis skill plan from this Docker integration test',
    session_id: expect.any(Number),
    client_request_id: expect.any(String)
  })
  expect(streamRequest.postDataJSON()).not.toHaveProperty('user_id')
  await expect(
    page.getByLabel('AI 求职顾问对话').getByText('Docker mock reply')
  ).toBeVisible()

  const redisCard = page.locator('.suggestion-card').filter({ hasText: 'Redis' }).last()
  await expect(redisCard).toBeVisible()

  const beforeSuggestionExport = await (await page.request.get('/api/career/export')).json()
  expect(beforeSuggestionExport.skills.filter((item) => item.skill === 'Redis')).toHaveLength(0)

  await redisCard.getByRole('button', { name: '编辑' }).click()
  const editor = page.getByRole('dialog', { name: /Redis|编辑技能计划建议/ })
  await expect(editor).toBeVisible()
  await editor.getByLabel('目标水平').fill('能独立设计缓存、限流和缓存穿透防护')
  await editor.getByRole('button', { name: '保存草稿' }).click()
  await expect(editor).toBeHidden()

  const stillPendingExport = await (await page.request.get('/api/career/export')).json()
  expect(stillPendingExport.skills.filter((item) => item.skill === 'Redis')).toHaveLength(0)

  await redisCard.getByRole('button', { name: '确认添加' }).click()
  await expect(redisCard).toContainText('已添加到技能计划')

  const acceptedExport = await (await page.request.get('/api/career/export')).json()
  const redisSkills = acceptedExport.skills.filter((item) => item.skill === 'Redis')
  expect(redisSkills).toHaveLength(1)
  expect(redisSkills[0]).toMatchObject({
    target_level: '能独立设计缓存、限流和缓存穿透防护',
    status: 'planned',
    progress: 0
  })

  const chatSessionId = streamRequest.postDataJSON().session_id
  const historyResponse = await page.request.get(`/api/sessions/${chatSessionId}/messages`)
  expect(historyResponse.status()).toBe(200)
  const historyMessages = await historyResponse.json()
  const acceptedSuggestion = historyMessages
    .flatMap((message) => message.suggestions || [])
    .find((suggestion) => suggestion.resource_type === 'skills' && suggestion.payload?.skill === 'Redis')
  expect(acceptedSuggestion).toMatchObject({ status: 'accepted', revision: 3 })

  const replayAccept = await page.request.post(
    `/api/career/suggestions/${acceptedSuggestion.id}/accept`,
    write({ revision: acceptedSuggestion.revision })
  )
  expect(replayAccept.status()).toBe(200)
  const replayExport = await (await page.request.get('/api/career/export')).json()
  expect(replayExport.skills.filter((item) => item.skill === 'Redis')).toHaveLength(1)

  await page.reload()
  await page.getByRole('button', { name: /继续职业对话/ }).click()
  const restoredCard = page.locator('.suggestion-card').filter({ hasText: 'Redis' }).last()
  await expect(restoredCard).toContainText('已添加到技能计划')

  const clearResponse = await page.request.delete(
    '/api/career/data',
    write({ confirmation: 'DELETE' })
  )
  expect(clearResponse.status()).toBe(200)
  const clearedExport = await (await page.request.get('/api/career/export')).json()
  for (const resource of ['resumes', 'jobs', 'applications', 'interviews', 'reports', 'skills']) {
    expect(clearedExport[resource]).toEqual([])
  }

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
