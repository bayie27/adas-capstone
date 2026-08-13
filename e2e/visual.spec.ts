import path from "node:path"
import { expect, test, type Locator, type Page } from "@playwright/test"

// Same .env read as login.spec.ts — the admin password is not hardcoded here.
try {
  process.loadEnvFile(path.resolve(import.meta.dirname, "..", ".env"))
} catch {
  // Ignore: e.g. .env already loaded into the environment by CI.
}

const ADMIN_PASSWORD = process.env.DEFAULT_ADMIN_PASSWORD
const API = "http://127.0.0.1:8000/api"

// Recharts animates path geometry from JS, not CSS, so killing transitions is
// not enough — the charts need long enough to land on their final frame.
const CHART_SETTLE_MS = 2000

const VIEWPORT = { width: 1440, height: 1024 } // the Figma artboard
const NO_MOTION = `*, *::before, *::after {
  transition: none !important; animation: none !important; caret-color: transparent !important;
}`

// One test, not nine. These routes share a single authenticated page, and any
// mechanism that splits them across tests has to keep that session alive
// between them; `test.describe.serial` does, but then the first failing route
// skips the other eight — which on Phase 2, where every route legitimately
// changes, would report one diff and hide the rest. A single test walking the
// list with soft assertions compares all nine and reports all nine, every run.
test("visual baselines for the nine routes", async ({ browser }) => {
  test.skip(!ADMIN_PASSWORD, "DEFAULT_ADMIN_PASSWORD is not set — copy .env.example to .env")
  test.setTimeout(240_000)

  // Seed from a throwaway context that is discarded before any page opens.
  //
  // This separation is load-bearing. Reseeding under a mounted app wipes the
  // user table, the backend's session sweep closes the socket with 4001, and
  // RealtimeAlertsBridge treats that as an expired session — clearSession()
  // then redirect to /login. The dev panel suppresses that with sessionEpoch
  // and suspendAuthRedirect; calling the API directly gets none of it. Doing
  // the reseed in a context that never renders the app sidesteps it entirely.
  const seeder = await browser.newContext()
  let openIds: number[]
  try {
    const login = await seeder.request.post(`${API}/auth/login`, {
      form: { username: "admin", password: ADMIN_PASSWORD as string },
    })
    expect(login.ok(), `login failed: ${login.status()} ${await login.text()}`).toBe(true)

    const reseed = await seeder.request.post(`${API}/dev/reseed`, { data: { profile: "demo" } })
    expect(reseed.ok(), `dev reseed failed: ${reseed.status()} ${await reseed.text()}`).toBe(true)

    // The demo profile seeds an Unverified incident, so GlobalAlerts opens its
    // accident dialog over every route (and starts the alarm). Pre-seed the
    // store's own "handled this session" set instead of dismissing the
    // incidents — that suppresses the dialog without mutating the data the
    // Detections tabs are meant to show.
    const res = await seeder.request.get(
      `${API}/alerts/?status=Unverified&status=Ongoing&limit=100`,
    )
    expect(res.ok(), `alert prefetch failed: ${res.status()}`).toBe(true)
    openIds = ((await res.json()).logs as { log_id: number }[]).map((l) => l.log_id)
  } finally {
    await seeder.close()
  }

  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 })
  await context.addInitScript((ids) => {
    sessionStorage.setItem("adas-handled-alert-ids", JSON.stringify(ids))
  }, openIds)

  async function settle(page: Page, route: string, { chart = false } = {}) {
    await page.goto(route)
    if (route !== "/login") {
      // A lost session redirects here, and every baseline silently becomes a
      // picture of the login form. Fail loudly instead — this is a hard
      // assertion, not a soft one: nothing below it is meaningful.
      await expect(page, `${route} bounced to /login — the session was lost`).not.toHaveURL(
        /\/login/,
      )
    }
    await expect(page.getByText(/Loading/i).first()).toBeHidden({ timeout: 15_000 })
    await page.waitForLoadState("networkidle")
    await page.addStyleTag({ content: NO_MOTION })
    if (chart) await page.waitForTimeout(CHART_SETTLE_MS)
  }

  /** Everything clock-derived on a page, masked rather than frozen (§6.5). */
  function masks(...locators: Locator[]) {
    return locators
  }

  // Timestamp (2) and Last Updated (6) on both Detections tabs.
  const DETECTION_DATE_COLUMNS = (p: Page) =>
    p.locator("tbody td:nth-child(2), tbody td:nth-child(6)")

  try {
    const page = await context.newPage()

    // --- /login, captured before signing in ---------------------------------
    await settle(page, "/login")
    await expect.soft(page).toHaveScreenshot("login.png", { fullPage: true })

    // Sign in through the form, not by planting a cookie. ProtectedRoute gates
    // on the Zustand auth store — the localStorage display cache of role and
    // username — so a valid session cookie alone still redirects to /login.
    // The soft assertion above cannot abort this.
    await page.getByPlaceholder("username").fill("admin")
    await page.getByPlaceholder("password").fill(ADMIN_PASSWORD as string)
    await page.getByRole("button", { name: "Login" }).click()
    await expect(page).toHaveURL(/\/admin$/)

    // --- the eight authenticated routes -------------------------------------
    await settle(page, "/admin", { chart: true })
    await expect
      .soft(page)
      // Every dashboard series is bucketed relative to now.
      .toHaveScreenshot("dashboard.png", {
        fullPage: true,
        mask: masks(page.locator(".recharts-wrapper")),
      })

    // Cameras: name / channel / connection / AI status / actions — no date
    // column, so nothing here drifts with the clock.
    await settle(page, "/admin/cameras")
    await expect.soft(page).toHaveScreenshot("cameras.png", { fullPage: true })

    // Detections: no. / TIMESTAMP / camera / status / handled by / LAST
    // UPDATED / actions. The demo profile seeds detected_at relative to now, so
    // both date columns roll over daily even though the row set is fixed.
    await settle(page, "/admin/detections")
    await expect.soft(page).toHaveScreenshot("detections-ongoing.png", {
      fullPage: true,
      mask: masks(DETECTION_DATE_COLUMNS(page)),
    })

    await page.getByRole("button", { name: /Logs/i }).click()
    await expect(page.getByText(/Loading/i).first()).toBeHidden({ timeout: 15_000 })
    await page.waitForLoadState("networkidle")
    await expect.soft(page).toHaveScreenshot("detections-logs.png", {
      fullPage: true,
      mask: masks(DETECTION_DATE_COLUMNS(page)),
    })

    await settle(page, "/admin/health", { chart: true })
    await expect.soft(page).toHaveScreenshot("system-health.png", {
      fullPage: true,
      // All four KPIs are live host telemetry (uptime, latency, fps, disk) and
      // the charts are time-bucketed. The card chrome around them is not, so
      // mask the value and subtext rather than the whole KPI row.
      mask: masks(
        page.locator(".recharts-wrapper"),
        page.locator(".text-3xl"),
        page.locator(".mt-4.text-xs"),
      ),
    })

    await settle(page, "/admin/ai", { chart: true })
    await expect.soft(page).toHaveScreenshot("ai-performance.png", {
      fullPage: true,
      mask: masks(page.locator(".recharts-wrapper")),
    })

    // Users: name / username / role / LAST LOGIN / actions.
    await settle(page, "/admin/users")
    await expect.soft(page).toHaveScreenshot("users.png", {
      fullPage: true,
      mask: masks(page.locator("tbody td:nth-child(4)")),
    })

    await settle(page, "/admin/profile")
    await expect.soft(page).toHaveScreenshot("profile-settings.png", { fullPage: true })
  } finally {
    await context.close()
  }
})
