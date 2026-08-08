import path from "node:path"
import { expect, test } from "@playwright/test"

// Reads the same repo-root .env the backend uses, so this stays correct
// even if DEFAULT_ADMIN_PASSWORD changes and isn't hardcoded here.
try {
  process.loadEnvFile(path.resolve(import.meta.dirname, "..", ".env"))
} catch {
  // Ignore: e.g. .env already loaded into the environment by CI.
}

const ADMIN_PASSWORD = process.env.DEFAULT_ADMIN_PASSWORD

test("admin can log in and reach the dashboard", async ({ page }) => {
  test.skip(!ADMIN_PASSWORD, "DEFAULT_ADMIN_PASSWORD is not set — copy .env.example to .env first")

  await page.goto("/login")

  await page.getByPlaceholder("username").fill("admin")
  await page.getByPlaceholder("password").fill(ADMIN_PASSWORD as string)
  await page.getByRole("button", { name: "Login" }).click()

  await expect(page).toHaveURL(/\/admin$/)
  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible()
})
