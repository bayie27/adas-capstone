import { expect, test } from "@playwright/test"

import {
  enrollFromLogin,
  getMfaAccount,
  loginWithAuthenticator,
  logoutFromUi,
  startPasswordFlow,
} from "./support/mfa"

test("a disposable user enrolls and then completes ordinary MFA login", async ({ page }) => {
  test.setTimeout(90_000)
  test.skip(
    process.env.E2E_LIVE_DEPLOYMENT === "1",
    "Enrollment is refused against live deployments; use the isolated E2E harness.",
  )
  if (process.env.MFA_E2E_MODE !== "isolated") {
    throw new Error("MFA browser login requires a fresh isolated E2E environment.")
  }

  const account = getMfaAccount("mfa-login")
  const passwordStage = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/auth/login",
  )
  const enrollment = await enrollFromLogin(page, account)
  const staged = await passwordStage
  expect(staged.status()).toBe(200)
  const challenge = await staged.json()
  expect(challenge.status).toBe("enrollment_required")
  expect(challenge).not.toHaveProperty("user")
  await expect(page).toHaveURL(/\/user$/)
  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible()

  await logoutFromUi(page)
  const secondStage = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/auth/login",
  )
  const acceptedStep = await loginWithAuthenticator(
    page,
    account,
    enrollment.secret,
    enrollment.step,
  )
  const challenged = await secondStage
  expect(challenged.status()).toBe(200)
  const secondChallenge = await challenged.json()
  expect(secondChallenge.status).toBe("mfa_required")
  expect(secondChallenge).not.toHaveProperty("user")
  expect(acceptedStep).toBeGreaterThan(enrollment.step)
  await expect(page).toHaveURL(/\/user$/)
})
