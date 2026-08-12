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

test.describe.configure({ mode: "serial" })

test.describe("visual baselines", () => {
  let page: Page

  test.beforeAll(async ({ browser }) => {
    test.skip(!ADMIN_PASSWORD, "DEFAULT_ADMIN_PASSWORD is not set — copy .env.example to .env")

    const context = await browser.newContext()
    page = await context.newPage()

    // Log in first: /api/dev/reseed is admin-gated. It wipes the database the
    // session belongs to and re-mints the cookie on the same context, so the
    // page stays authenticated across the reseed.
    await page.goto("/login")
    await page.getByPlaceholder("username").fill("admin")
    await page.getByPlaceholder("password").fill(ADMIN_PASSWORD as string)
    await page.getByRole("button", { name: "Login" }).click()
    await expect(page).toHaveURL(/\/admin$/)

    const reseed = await page.request.post(`${API}/dev/reseed`, {
      data: { profile: "demo" },
    })
    expect(reseed.ok(), `dev reseed failed: ${reseed.status()} ${await reseed.text()}`).toBe(true)

    // The demo profile seeds an Unverified incident, so GlobalAlerts opens its
    // accident dialog over every route (and starts the alarm). Pre-seed the
    // store's own "handled this session" set instead of dismissing the
    // incidents — that suppresses the dialog without mutating the dataset the
    // Detections tabs are meant to show.
    const open = await page.request.get(`${API}/alerts/?status=Unverified&status=Ongoing&limit=100`)
    expect(open.ok(), `alert prefetch failed: ${open.status()}`).toBe(true)
    const openIds = ((await open.json()).logs as { log_id: number }[]).map((l) => l.log_id)
    await page.addInitScript((ids) => {
      sessionStorage.setItem("adas-handled-alert-ids", JSON.stringify(ids))
    }, openIds)
  })

  test.afterAll(async () => {
    await page?.context().close()
  })

  /** Everything clock-derived on a page, masked rather than frozen (§6.5). */
  function masks(...locators: Locator[]) {
    return locators
  }

  async function settle(route: string, { chart = false } = {}) {
    await page.goto(route)
    await expect(page.getByText(/Loading/i).first()).toBeHidden({ timeout: 15_000 })
    await page.waitForLoadState("networkidle")
    // Kill CSS transitions and the caret; neither is deterministic frame-to-frame.
    await page.addStyleTag({
      content: `*, *::before, *::after { transition: none !important; animation: none !important; caret-color: transparent !important; }`,
    })
    if (chart) await page.waitForTimeout(CHART_SETTLE_MS)
  }

  test("login", async () => {
    await page.context().clearCookies()
    await settle("/login")
    await expect(page).toHaveScreenshot("login.png", { fullPage: true })

    // Restore the session for the remaining routes.
    await page.getByPlaceholder("username").fill("admin")
    await page.getByPlaceholder("password").fill(ADMIN_PASSWORD as string)
    await page.getByRole("button", { name: "Login" }).click()
    await expect(page).toHaveURL(/\/admin$/)
  })

  test("dashboard", async () => {
    await settle("/admin", { chart: true })
    await expect(page).toHaveScreenshot("dashboard.png", {
      fullPage: true,
      // Every dashboard series is bucketed relative to now.
      mask: masks(page.locator(".recharts-wrapper")),
    })
  })

  test("cameras", async () => {
    await settle("/admin/cameras")
    await expect(page).toHaveScreenshot("cameras.png", {
      fullPage: true,
      mask: masks(page.locator("tbody td:nth-child(6)")),
    })
  })

  test("detections-ongoing", async () => {
    await settle("/admin/detections")
    await expect(page).toHaveScreenshot("detections-ongoing.png", {
      fullPage: true,
      mask: masks(page.locator("tbody td:nth-child(3)")),
    })
  })

  test("detections-logs", async () => {
    await settle("/admin/detections")
    await page.getByRole("button", { name: /Logs/i }).click()
    await expect(page.getByText(/Loading/i).first()).toBeHidden({ timeout: 15_000 })
    await page.waitForLoadState("networkidle")
    await expect(page).toHaveScreenshot("detections-logs.png", {
      fullPage: true,
      mask: masks(page.locator("tbody td:nth-child(3)"), page.locator("tbody td:nth-child(6)")),
    })
  })

  test("system-health", async () => {
    await settle("/admin/health", { chart: true })
    await expect(page).toHaveScreenshot("system-health.png", {
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
  })

  test("ai-performance", async () => {
    await settle("/admin/ai", { chart: true })
    await expect(page).toHaveScreenshot("ai-performance.png", {
      fullPage: true,
      mask: masks(page.locator(".recharts-wrapper")),
    })
  })

  test("users", async () => {
    await settle("/admin/users")
    await expect(page).toHaveScreenshot("users.png", {
      fullPage: true,
      // Last Login renders as a relative string.
      mask: masks(page.locator("tbody td:nth-child(5)")),
    })
  })

  test("profile-settings", async () => {
    await settle("/admin/profile")
    await expect(page).toHaveScreenshot("profile-settings.png", { fullPage: true })
  })
})
