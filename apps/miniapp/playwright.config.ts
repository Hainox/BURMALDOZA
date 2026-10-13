import { defineConfig, devices } from '@playwright/test';

// E2E_PORT меняет порт, если локально 4173 уже занят другим сервером:
// иначе reuseExistingServer молча подключится к чужому сайту.
const port = Number(process.env.E2E_PORT ?? 4173);
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL,
    trace: 'on-first-retry'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ],
  webServer: {
    command: `pnpm build && pnpm exec vite preview --host 127.0.0.1 --port ${port} --strictPort`,
    url: baseURL,
    env: { PUBLIC_API_BASE_URL: baseURL },
    reuseExistingServer: !process.env.CI
  }
});
