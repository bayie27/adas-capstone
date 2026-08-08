import { defineConfig, devices } from "@playwright/test"

// E2E spans both the backend and the frontend, so this lives at the repo
// root rather than inside frontend/. CI-only — excluded from `pnpm check`.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "uv run fastapi run backend/app/main.py --port 8000",
      url: "http://127.0.0.1:8000/docs",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      // --host 127.0.0.1 is required: Vite's default `localhost` host resolves
      // to the IPv6 loopback here, which 127.0.0.1 (used below and by the
      // backend's hardcoded CORS allowlist) can't reach.
      command: "pnpm --filter frontend dev --port 5173 --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
