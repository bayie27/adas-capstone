import { defineConfig, devices } from "@playwright/test"

// E2E spans both the backend and the frontend, so this lives at the repo
// root rather than inside frontend/. Runs locally before PRs and in CI;
// excluded from `pnpm check`.
const isLiveDeployment = process.env.E2E_LIVE_DEPLOYMENT === "1"
if (isLiveDeployment && !process.env.E2E_BASE_URL) {
  throw new Error("E2E_BASE_URL must be set when E2E_LIVE_DEPLOYMENT=1")
}

const baseURL = isLiveDeployment ? process.env.E2E_BASE_URL : "http://127.0.0.1:5173"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  // The comment this replaces claimed 1% "absorbs antialiasing without hiding a
  // real palette change". It did the opposite, and Phase 2 proved it: a
  // complete re-palette of all nine routes passed green.
  //
  // The reason is `threshold`, which was left at Playwright's default of 0.2.
  // It is a PER-PIXEL YIQ distance, and a pixel only counts as different once
  // that distance exceeds 35215 x 0.2^2 = 1409. A design-token swap moves
  // colours a tiny fraction of that:
  //
  //     #0A0A0A -> #09090B (canvas)       delta    0.5
  //     #141414 -> #121212 (card)         delta    2
  //     #737373 -> #A1A1AA (muted text)   delta 1069
  //
  // All under the cut-off, so ~99% of a changed page counted as unchanged and
  // maxDiffPixelRatio never came into play. Measured at threshold 0, 70-99.6%
  // of every route actually differs.
  //
  // Antialiasing was never what `threshold` was absorbing — AA jitter swings a
  // pixel between dark and light, which scores far ABOVE 1409 and is caught by
  // maxDiffPixelRatio instead. So tightening the threshold costs almost no
  // noise tolerance and buys back the entire point of the harness.
  //
  // Measured on this suite: at threshold 0.02 the token change registers
  // 1.1-22% of pixels on eight of the nine routes, while run-to-run noise
  // against a baseline from identical code peaks at ~0.39% (glyph-edge jitter
  // on the two busiest tables). 0.5% sits between them.
  //
  // Known blind spot: /login is 0.11% — almost all of that page is flat canvas
  // whose #0A0A0A -> #09090B shift is genuinely sub-perceptual — so its
  // baseline is refreshed without a diff to review.
  expect: {
    toHaveScreenshot: { threshold: 0.02, maxDiffPixelRatio: 0.005 },
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
  webServer: isLiveDeployment
    ? []
    : [
        {
          command: "uv run fastapi run backend/app/main.py --port 8000",
          url: "http://127.0.0.1:8000/docs",
          // FastAPI's Rich startup banner contains an emoji.  The Playwright
          // web server is a detached Windows process, so pin UTF-8 here just
          // as the controlled maintenance/startup launchers do.
          env: { ...process.env, PYTHONUTF8: "1" },
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
