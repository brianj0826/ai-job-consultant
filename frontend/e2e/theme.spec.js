import { expect, test } from '@playwright/test'

const openWithTheme = async (page, { colorScheme, savedTheme }) => {
  await page.emulateMedia({ colorScheme })
  await page.addInitScript((theme) => {
    if (theme === null) localStorage.removeItem('ai_dark_mode')
    else localStorage.setItem('ai_dark_mode', theme)
  }, savedTheme)
  await page.goto('/login')
}

test.describe('theme initialization', () => {
  test('prefers a saved light choice over a dark system preference', async ({ page }) => {
    await openWithTheme(page, { colorScheme: 'dark', savedTheme: '0' })

    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
    await expect(page.locator('html')).not.toHaveClass(/(^|\s)dark(\s|$)/)
  })

  test('prefers a saved dark choice over a light system preference', async ({ page }) => {
    await openWithTheme(page, { colorScheme: 'light', savedTheme: '1' })

    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
    await expect(page.locator('html')).toHaveClass(/(^|\s)dark(\s|$)/)
  })

  test('follows the system preference when no choice has been saved', async ({ page }) => {
    await openWithTheme(page, { colorScheme: 'dark', savedTheme: null })

    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
    await expect(page.locator('html')).toHaveClass(/(^|\s)dark(\s|$)/)
  })
})
