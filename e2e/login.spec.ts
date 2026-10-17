import { expect, test } from "@playwright/test"

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD
const ISOLATED_API_ORIGIN = process.env.E2E_BACKEND_ORIGIN

test("admin can log in and reach the dashboard", async ({ page }) => {
  test.skip(!ADMIN_PASSWORD, "E2E_ADMIN_PASSWORD is not configured for this run")
  if (
    process.env.MFA_E2E_MODE === "isolated" &&
    process.env.DEFAULT_ADMIN_PASSWORD !== ADMIN_PASSWORD
  ) {
    throw new Error("The browser and backend do not share the disposable admin credential")
  }

  let blockedApiOrigin: string | undefined
  if (process.env.MFA_E2E_MODE === "isolated") {
    if (!ISOLATED_API_ORIGIN) {
      throw new Error("E2E_BACKEND_ORIGIN is required for the isolated browser run")
    }
    await page.route("**/*", async (route) => {
      const requestUrl = new URL(route.request().url())
      if (requestUrl.pathname.startsWith("/api/") && requestUrl.origin !== ISOLATED_API_ORIGIN) {
        const requestOrigin = requestUrl.origin
        blockedApiOrigin = requestOrigin
        await route.abort()
        return
      }
      await route.continue()
    })
  }

  await page.goto("/login")

  await page.getByPlaceholder("username").fill("admin")
  const passwordInput = page.getByPlaceholder("password")
  await passwordInput.fill(ADMIN_PASSWORD as string)
  if ((await passwordInput.inputValue()) !== ADMIN_PASSWORD) {
    throw new Error("The password input did not retain the disposable credential")
  }
  let submittedCredentialsMatch = false
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/api/auth/login") {
      const body = new URLSearchParams(request.postData() ?? "")
      submittedCredentialsMatch =
        body.get("username") === "admin" && body.get("password") === ADMIN_PASSWORD
    }
  })
  const loginResponsePromise = page
    .waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname === "/api/auth/login",
    )
    .catch(() => null)
  await page.getByRole("button", { name: "Login" }).click()
  const loginResponse = await loginResponsePromise
  if (blockedApiOrigin) {
    throw new Error(`Blocked API request outside the isolated backend: ${blockedApiOrigin}`)
  }
  if (!loginResponse) {
    throw new Error("The password login API did not return a response")
  }
  if (!submittedCredentialsMatch) {
    throw new Error("The browser did not submit the disposable credentials unchanged")
  }
  expect(loginResponse.status()).toBe(200)

  await expect(page).toHaveURL(/\/admin$/)
  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible()
})
