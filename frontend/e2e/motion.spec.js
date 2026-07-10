import { expect, test } from '@playwright/test'

const installMotionMetrics = async (page) => {
  await page.addInitScript(() => {
    window.__motionMetrics = { cls: 0, frameTimes: [], longTasks: [] }

    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) window.__motionMetrics.cls += entry.value
        }
      }).observe({ type: 'layout-shift', buffered: true })

      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          window.__motionMetrics.longTasks.push(entry.duration)
        }
      }).observe({ type: 'longtask', buffered: true })
    } catch {
      // Some browser builds do not expose every performance entry type.
    }

    let previousFrame = performance.now()
    const sampleFrame = (time) => {
      window.__motionMetrics.frameTimes.push(time - previousFrame)
      previousFrame = time
      requestAnimationFrame(sampleFrame)
    }
    requestAnimationFrame(sampleFrame)
  })
}

const authenticateFromStorage = async (page) => {
  await page.addInitScript(() => {
    localStorage.setItem('ai_user_id', '7')
    localStorage.setItem('ai_username', '动效测试用户')
  })
}

const openAuthenticatedChat = async (page) => {
  await authenticateFromStorage(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '职业工作台' })).toBeVisible()
  await page.getByRole('button', { name: /岗位精准匹配/ }).click()
  await expect(page.getByRole('heading', { name: '职业智能对话' })).toBeVisible()
  await expect.poll(() => page.locator('.msg-row--assistant').count()).toBeGreaterThanOrEqual(25)
  await expect(page.locator('.streaming-status')).toBeHidden()
  await expect(page.getByRole('textbox', { name: '向职达 AI 提问' })).toBeEnabled()
}

const expectNoHorizontalOverflow = async (page) => {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth
  }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1)
}

test.describe('responsive motion flows', () => {
  test('login and registration keep the form anchored and focus the first invalid field', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/')

    const card = page.locator('.welcome-card')
    const initialBox = await card.boundingBox()
    await page.locator('.mode-link').click()
    await expect(page.getByPlaceholder('请再次输入密码')).toBeEnabled()

    const registerBox = await card.boundingBox()
    expect(Math.abs((registerBox?.y || 0) - (initialBox?.y || 0))).toBeLessThanOrEqual(8)

    await page.locator('.submit-btn').click()
    await expect(page.getByPlaceholder('请输入用户名')).toBeFocused()
    await expect(page.locator('.el-form-item__error').filter({ hasText: '请输入用户名' })).toHaveCount(1)

    await page.locator('.mode-link').click()
    await expect(page.getByPlaceholder('请再次输入密码')).toBeDisabled()
    await expectNoHorizontalOverflow(page)
  })

  for (const viewport of [
    { name: 'mobile', width: 390, height: 844 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'desktop', width: 1440, height: 900 }
  ]) {
    test(`${viewport.name} keeps navigation and view changes continuous`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })
      await page.goto('/?preview=1')
      await expect(page.getByRole('heading', { name: '职业工作台' })).toBeVisible()
      await expectNoHorizontalOverflow(page)

      if (viewport.width < 1280) {
        const navigationToggle = page.getByRole('button', { name: '打开导航' })
        await navigationToggle.click()

        const navigation = page.locator('#app-navigation')
        await expect(navigation).not.toHaveAttribute('aria-hidden', 'true')

        const closeButton = navigation.getByRole('button', { name: '关闭导航' })
        const closeBox = await closeButton.boundingBox()
        expect(closeBox?.width || 0).toBeGreaterThanOrEqual(44)
        expect(closeBox?.height || 0).toBeGreaterThanOrEqual(44)

        await closeButton.click()
        await expect(navigationToggle).toBeFocused()
        await expect(navigation).toHaveAttribute('aria-hidden', 'true')
      }

      await page.getByRole('button', { name: /岗位精准匹配/ }).click()
      await expect(page.getByRole('heading', { name: '职业智能对话' })).toBeVisible()
      await expectNoHorizontalOverflow(page)
    })
  }

  test('drawer opens and closes without losing the active view', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/?preview=1')
    await page.getByRole('button', { name: '数据' }).click()

    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('heading', { name: '数据分析' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(page.getByRole('heading', { name: '职业工作台' })).toBeVisible()
  })
})

test.describe('streaming continuity', () => {
  test('an interrupted reply preserves content and retries without a duplicate user message', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await openAuthenticatedChat(page)

    const composer = page.getByRole('textbox', { name: '向职达 AI 提问' })
    const interruptionPrompt = `请模拟中断-${testInfo.retry}`
    await composer.fill(interruptionPrompt)
    await page.getByRole('button', { name: '发送消息' }).click()

    await expect(page.getByText('生成中断')).toBeVisible()
    await expect(page.getByText('这段已经生成的内容必须在连接中断后保留。')).toBeVisible()
    await expect(page.locator('.msg-row--user').filter({ hasText: interruptionPrompt })).toHaveCount(1)

    await page.getByRole('button', { name: '重新尝试' }).click()
    await expect(page.locator('.message-list').getByText('重试后的完整回复已生成。', { exact: true })).toBeVisible()
    await expect(page.locator('.msg-row--user').filter({ hasText: interruptionPrompt })).toHaveCount(1)
  })

  test('a ten-second stream does not take scrolling control from the user', async ({ page }, testInfo) => {
    test.setTimeout(30_000)
    await installMotionMetrics(page)
    await page.setViewportSize({ width: 1440, height: 900 })
    await openAuthenticatedChat(page)

    const composer = page.getByRole('textbox', { name: '向职达 AI 提问' })
    await composer.fill('性能流')
    await page.getByRole('button', { name: '发送消息' }).click()
    const streamingStatus = page.locator('.streaming-status')
    await expect(streamingStatus).toBeVisible()

    await page.evaluate(() => {
      window.__motionMetrics.cls = 0
      window.__motionMetrics.frameTimes = []
      window.__motionMetrics.longTasks = []
    })
    await page.waitForTimeout(100)

    const messageList = page.locator('.message-list')
    await messageList.evaluate((element) => {
      element.scrollTop = 0
      element.dispatchEvent(new Event('scroll'))
    })
    await expect(page.getByRole('button', { name: '回到最新' })).toBeVisible()

    await expect(streamingStatus).toBeHidden({ timeout: 20_000 })
    expect(await messageList.evaluate((element) => element.scrollTop)).toBeLessThanOrEqual(1)

    const finalReply = page.locator('.msg-row--assistant .message-content').last()
    expect((await finalReply.innerText()).length).toBeGreaterThanOrEqual(1000)

    const metrics = await page.evaluate(() => {
      const values = [...window.__motionMetrics.frameTimes].sort((a, b) => a - b)
      const p95Index = Math.max(0, Math.ceil(values.length * 0.95) - 1)
      const droppedFrames = values.filter((value) => value > 33.3).length
      return {
        cls: window.__motionMetrics.cls,
        frameSamples: values.length,
        p95FrameTime: values[p95Index] || 0,
        droppedFrameRate: values.length ? droppedFrames / values.length : 0,
        longTasks: window.__motionMetrics.longTasks
      }
    })

    await testInfo.attach('motion-performance.json', {
      body: JSON.stringify(metrics, null, 2),
      contentType: 'application/json'
    })
    expect(metrics.cls).toBeLessThan(0.1)
  })
})

test('reduced motion disables CSS movement', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')

  expect(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true)

  const duration = await page.locator('.welcome-card').evaluate((element) => {
    const styles = getComputedStyle(element)
    const toSeconds = (value) => value.trim().endsWith('ms')
      ? (Number.parseFloat(value) || 0) / 1000
      : Number.parseFloat(value) || 0
    return Math.max(
      ...styles.animationDuration.split(',').map(toSeconds),
      ...styles.transitionDuration.split(',').map(toSeconds)
    )
  })
  expect(duration).toBeLessThanOrEqual(0.00001)

  await page.evaluate(() => {
    localStorage.setItem('ai_user_id', '7')
    localStorage.setItem('ai_username', '动效测试用户')
  })
  await page.reload()
  await expect(page.getByRole('heading', { name: '职业工作台' })).toBeVisible()
  await page.getByRole('button', { name: '数据' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()

  const drawerDuration = await page.getByRole('dialog').evaluate((element) => {
    const values = getComputedStyle(element).transitionDuration.split(',')
    return Math.max(...values.map((value) => value.trim().endsWith('ms')
      ? (Number.parseFloat(value) || 0) / 1000
      : Number.parseFloat(value) || 0))
  })
  expect(drawerDuration).toBeLessThanOrEqual(0.00001)

  const progress = page.locator('.el-progress-bar__inner')
  await expect.poll(() => progress.count()).toBeGreaterThan(0)
  expect(await progress.first().evaluate((element) => getComputedStyle(element).transitionDuration)).toBe('0s')
})
