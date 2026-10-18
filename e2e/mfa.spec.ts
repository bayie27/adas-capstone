import { expect, test, type WebSocket } from "@playwright/test"

import {
  acknowledgeRecoveryCodes,
  enrollFromLogin,
  enterFreshTotp,
  getMfaAccount,
  loginWithAuthenticator,
  logoutFromUi,
  readManualKey,
  readRecoveryCodes,
  startPasswordFlow,
  wrongTotpCode,
} from "./support/mfa"

test.beforeEach(() => {
  test.setTimeout(90_000)
  test.skip(
    process.env.E2E_LIVE_DEPLOYMENT === "1",
    "Enrollment, recovery, replacement, and rotation are refused against live deployments.",
  )
  if (process.env.MFA_E2E_MODE !== "isolated") {
    throw new Error("MFA browser scenarios require a fresh isolated E2E environment.")
  }
})

test("recovery consumes one code, enrolls a replacement factor, and supports a fresh login", async ({
  page,
}) => {
  const account = getMfaAccount("mfa-recovery")
  const initial = await enrollFromLogin(page, account)
  const recoveryCode = initial.recoveryCodes[0]

  await logoutFromUi(page)
  await startPasswordFlow(page, account)
  await expect(page.getByRole("heading", { name: "Verify your sign-in" })).toBeVisible()
  await page.getByRole("button", { name: "Use a recovery code" }).click()
  await page.getByLabel("Recovery code").fill(recoveryCode)
  await page.getByRole("button", { name: "Verify code" }).click()
  await page
    .getByRole("heading", { name: "Set up your authenticator" })
    .waitFor({ state: "visible" })

  const replacementSeed = await readManualKey(page)
  const replacementStep = await enterFreshTotp(page, replacementSeed)
  await page.getByRole("button", { name: "Confirm authenticator" }).click()
  const replacementCodes = await readRecoveryCodes(page)
  expect(replacementCodes.includes(recoveryCode)).toBe(false)
  await acknowledgeRecoveryCodes(page)
  await expect(page).toHaveURL(/\/user$/)

  await logoutFromUi(page)
  const acceptedStep = await loginWithAuthenticator(page, account, replacementSeed, replacementStep)
  expect(acceptedStep).toBeGreaterThan(replacementStep)
  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible()
})

test("replacement codes survive session clearing and the closed WebSocket", async ({ page }) => {
  const account = getMfaAccount("mfa-replacement")
  const activeAlertSockets = new Set<WebSocket>()
  let resolveRevocationClose: (() => void) | null = null
  page.on("websocket", (socket) => {
    if (new URL(socket.url()).pathname !== "/ws/alerts") return
    activeAlertSockets.add(socket)
    socket.on("close", () => {
      activeAlertSockets.delete(socket)
      resolveRevocationClose?.()
    })
  })
  const initial = await enrollFromLogin(page, account)

  // `goto` unloads the dashboard document and closes its WebSocket. Track the
  // profile document's live connection, including any reconnects during load.
  await page.goto("/user/profile")
  await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible()
  await expect.poll(() => activeAlertSockets.size).toBeGreaterThan(0)
  await expect(page.getByText(/10 recovery codes remaining/i)).toBeVisible()
  await page.getByRole("button", { name: "Replace authenticator" }).click()
  await page.getByLabel("Current password").fill(account.password)
  await enterFreshTotp(page, initial.secret, initial.step, "Current authenticator code")
  await page.getByRole("button", { name: "Start replacement" }).click()
  await page.getByLabel("Authenticator code").waitFor({ state: "visible" })

  const replacementSeed = await readManualKey(page)
  const replacementStep = await enterFreshTotp(page, replacementSeed)
  const closedPromise = new Promise<void>((resolve) => {
    resolveRevocationClose = resolve
  })
  const confirmationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/auth/mfa/enrollment/confirm",
  )
  await page.getByRole("button", { name: "Confirm authenticator" }).click()
  const response = await confirmationResponse
  expect(response.status()).toBe(200)

  const dialog = page.getByRole("dialog", { name: "Save your recovery codes" })
  await dialog.waitFor({ state: "visible" })
  await page.waitForURL(/\/login$/)
  await page.getByRole("list", { name: "One-time recovery codes" }).waitFor({ state: "visible" })
  await closedPromise

  await acknowledgeRecoveryCodes(page)
  const acceptedStep = await loginWithAuthenticator(page, account, replacementSeed, replacementStep)
  expect(acceptedStep).toBeGreaterThan(replacementStep)
  await expect(page).toHaveURL(/\/user$/)
})

test("recovery-code rotation keeps the session and invalidates its previous batch", async ({
  page,
}) => {
  const account = getMfaAccount("mfa-rotation")
  const initial = await enrollFromLogin(page, account)
  const previousCode = initial.recoveryCodes[0]

  await page.goto("/user/profile")
  await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible()
  await page.getByRole("button", { name: "Rotate recovery codes" }).click()
  await page.getByLabel("Password", { exact: true }).fill(account.password)
  await enterFreshTotp(page, initial.secret, initial.step, "Current authenticator code")
  await page.getByRole("button", { name: "Rotate codes" }).click()

  const newCodes = await readRecoveryCodes(page)
  expect(newCodes.includes(previousCode)).toBe(false)
  await acknowledgeRecoveryCodes(page)
  await expect(page).toHaveURL(/\/user\/profile$/)
  await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible()

  await logoutFromUi(page)
  await startPasswordFlow(page, account)
  await expect(page.getByRole("heading", { name: "Verify your sign-in" })).toBeVisible()
  await page.getByRole("button", { name: "Use a recovery code" }).click()
  await page.getByLabel("Recovery code").fill(previousCode)
  await page.getByRole("button", { name: "Verify code" }).click()
  await expect(page.getByRole("alert")).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
})

test("wrong TOTP proofs stay inline and reach the server-driven retry countdown", async ({
  page,
}) => {
  const account = getMfaAccount("mfa-wrong-code")
  const enrolled = await enrollFromLogin(page, account)
  await logoutFromUi(page)
  await startPasswordFlow(page, account)
  await expect(page.getByRole("heading", { name: "Verify your sign-in" })).toBeVisible()

  const invalidCode = wrongTotpCode(enrolled.secret)
  const codeInput = page.getByLabel("Authenticator code")
  let unauthorizedAttempts = 0
  let blocked = false
  for (let attempt = 0; attempt < 11; attempt += 1) {
    await codeInput.fill(invalidCode)
    const responsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname === "/api/auth/mfa/verify",
    )
    await page.getByRole("button", { name: /verify code/i }).click()
    const response = await responsePromise
    if (response.status() === 429) {
      blocked = true
      break
    }
    expect(response.status()).toBe(401)
    unauthorizedAttempts += 1
  }

  // Earlier cases can use the shared IP bucket (for example, rejecting a
  // rotated recovery code), so the limiter may have prior failures recorded.
  expect(unauthorizedAttempts).toBeGreaterThan(0)
  expect(blocked).toBe(true)
  await expect(page.getByText(/wait \d+s before trying another code/i)).toBeVisible()
  await expect(page.getByRole("button", { name: /try again in \d+s/i })).toBeDisabled()
  await expect(page).toHaveURL(/\/login$/)
})
