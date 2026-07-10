import { defineConfig, devices } from '@playwright/test'

const frontendPort = Number.parseInt(process.env.E2E_FRONTEND_PORT || '4174', 10)
const mockApiPort = Number.parseInt(process.env.E2E_API_PORT || '8001', 10)
const frontendOrigin = `http://127.0.0.1:${frontendPort}`

export default defineConfig({
  testDir: './e2e',
  testIgnore: '**/docker-smoke.spec.js',
  outputDir: './output/playwright/test-results',
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 35_000,
  expect: {
    timeout: 6_000
  },
  fullyParallel: false,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: './output/playwright/report', open: 'never' }]
  ],
  use: {
    baseURL: frontendOrigin,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ],
  webServer: [
    {
      command: `npx vite --mode e2e --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      url: frontendOrigin,
      env: { ...process.env, E2E_API_PORT: String(mockApiPort) },
      reuseExistingServer: false,
      timeout: 120_000
    },
    {
      command: 'node e2e/mock-api.mjs',
      url: `http://127.0.0.1:${mockApiPort}/api/health`,
      env: { ...process.env, MOCK_API_PORT: String(mockApiPort) },
      reuseExistingServer: false,
      timeout: 120_000
    }
  ]
})
