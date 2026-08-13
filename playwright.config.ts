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
  // Antialiasing differs enough between machines to trip a byte-exact compare;
  // 1% absorbs that without hiding a real palette change.
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.01 },
  },
  projects: [
    {
      name: "chromium",
      // The visual project is deliberately outside the default run: `test:e2e`
      // feeds `full:check`, and a screenshot diff failing the pre-PR gate on a
      // legitimate design change would be noise (FE_Implementation.md §6.5).
      testIgnore: /visual\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "visual",
      testMatch: /visual\.spec\.ts/,
      // No retries here, unlike the default project. A retry re-runs the whole
      // serial block and passes a route whose baseline the failed attempt just
      // wrote, which hides both a missing baseline and a genuine flake — and a
      // flaky baseline is worse than no baseline (§6.5).
      retries: 0,
      // One worker, in order: the tests share a single authenticated page.
      fullyParallel: false,
      use: {
        ...devices["Desktop Chrome"],
        // The Figma artboard. deviceScaleFactor 1 keeps the baselines at CSS
        // pixel size rather than 2x.
        viewport: { width: 1440, height: 1024 },
        deviceScaleFactor: 1,
      },
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
