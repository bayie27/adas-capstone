import { createHmac } from "node:crypto"
import type { Page } from "@playwright/test"
import { expect } from "@playwright/test"

const BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

export interface E2EMfaAccount {
  username: string
  password: string
}

export function getMfaAccount(username: string): E2EMfaAccount {
  const accounts = JSON.parse(process.env.E2E_MFA_ACCOUNTS ?? "{}") as Record<string, string>
  const password = accounts[username]
  if (!password) throw new Error("A disposable MFA account is not configured for this run.")
  return { username, password }
}

function decodeBase32(secret: string): Buffer {
  let buffer = 0
  let bitsLeft = 0
  const bytes: number[] = []
  for (const character of secret.toUpperCase().replace(/=+$/g, "")) {
    const value = BASE32_ALPHABET.indexOf(character)
    if (value < 0) throw new Error("The authenticator setup key is invalid.")
    buffer = (buffer << 5) | value
    bitsLeft += 5
    if (bitsLeft >= 8) {
      bitsLeft -= 8
      bytes.push((buffer >> bitsLeft) & 0xff)
    }
  }
  return Buffer.from(bytes)
}

export function totpCode(secret: string, timestampSeconds: number, digits = 6): string {
  const counter = Buffer.alloc(8)
  counter.writeBigUInt64BE(BigInt(Math.floor(timestampSeconds / 30)))
  const digest = createHmac("sha1", decodeBase32(secret)).update(counter).digest()
  const offset = digest[digest.length - 1] & 0x0f
  const value =
    (((digest[offset] & 0x7f) << 24) |
      ((digest[offset + 1] & 0xff) << 16) |
      ((digest[offset + 2] & 0xff) << 8) |
      (digest[offset + 3] & 0xff)) %
    10 ** digits
  return String(value).padStart(digits, "0")
}

export function totpStep(timestampSeconds = Date.now() / 1000): number {
  return Math.floor(timestampSeconds / 30)
}

export function wrongTotpCode(secret: string, timestampSeconds = Date.now() / 1000): string {
  const valid = new Set(
    [-2, -1, 0, 1, 2].map((offset) =>
      totpCode(secret, (totpStep(timestampSeconds) + offset) * 30, 6),
    ),
  )
  for (let candidate = 0; candidate < 1_000_000; candidate += 1) {
    const code = String(candidate).padStart(6, "0")
    if (!valid.has(code)) return code
  }
  throw new Error("Could not construct a disposable invalid authenticator code.")
}

export async function enterFreshTotp(
  page: Page,
  secret: string,
  afterStep = -1,
  label = "Authenticator code",
): Promise<number> {
  while (true) {
    const now = Date.now() / 1000
    const step = totpStep(now)
    const secondsRemaining = 30 - (Math.floor(now) % 30)
    if (step > afterStep && secondsRemaining > 9) {
      await page.getByLabel(label).fill(totpCode(secret, now))
      return step
    }
    await page.waitForTimeout(Math.max(250, Math.min(3000, (secondsRemaining + 1) * 1000)))
  }
}

export async function startPasswordFlow(page: Page, account: E2EMfaAccount): Promise<void> {
  await page.goto("/login")
  await page.getByLabel("Username").fill(account.username)
  await page.getByLabel("Password", { exact: true }).fill(account.password)
  await page.getByRole("button", { name: "Continue" }).click()
}

export async function readRecoveryCodes(page: Page): Promise<string[]> {
  await page
    .getByRole("heading", { name: "Save your recovery codes" })
    .waitFor({ state: "visible" })
  return page.getByRole("list", { name: "One-time recovery codes" }).locator("code").allInnerTexts()
}

export async function readManualKey(page: Page): Promise<string> {
  await page.getByText("Can't scan? Enter this key:").waitFor({ state: "visible" })
  return (await page.locator("code").first().innerText()).trim()
}

export async function acknowledgeRecoveryCodes(page: Page): Promise<void> {
  await page.getByRole("checkbox", { name: /i saved these codes/i }).check()
  await page.getByRole("button", { name: "Continue" }).click()
}

export async function enrollFromLogin(
  page: Page,
  account: E2EMfaAccount,
): Promise<{ secret: string; step: number; recoveryCodes: string[] }> {
  await startPasswordFlow(page, account)
  await page
    .getByRole("heading", { name: "Set up your authenticator" })
    .waitFor({ state: "visible" })
  await page.getByLabel("Authenticator code").waitFor({ state: "visible" })
  const secret = await readManualKey(page)
  const step = await enterFreshTotp(page, secret)
  await page.getByRole("button", { name: "Confirm authenticator" }).click()
  const recoveryCodes = await readRecoveryCodes(page)
  await acknowledgeRecoveryCodes(page)
  return { secret, step, recoveryCodes }
}

export async function loginWithAuthenticator(
  page: Page,
  account: E2EMfaAccount,
  secret: string,
  afterStep = -1,
): Promise<number> {
  await startPasswordFlow(page, account)
  await expect(page.getByRole("heading", { name: "Verify your sign-in" })).toBeVisible()
  const step = await enterFreshTotp(page, secret, afterStep)
  await page.getByRole("button", { name: "Verify code" }).click()
  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible()
  return step
}

export async function logoutFromUi(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Log Out" }).click()
  await expect(page).toHaveURL(/\/login$/)
}
