import { afterEach, describe, expect, it, vi } from "vitest"

const liveEnvironmentKeys = ["E2E_LIVE_DEPLOYMENT", "E2E_BASE_URL"] as const
const originalEnvironment = Object.fromEntries(
  liveEnvironmentKeys.map((key) => [key, process.env[key]]),
)

async function loadConfig(
  environment: Partial<Record<(typeof liveEnvironmentKeys)[number], string>>,
) {
  for (const key of liveEnvironmentKeys) {
    const value = environment[key]
    if (value === undefined) delete process.env[key]
    else process.env[key] = value
  }

  vi.resetModules()
  return (await import("./playwright.config")).default
}

afterEach(() => {
  for (const key of liveEnvironmentKeys) {
    const value = originalEnvironment[key]
    if (value === undefined) delete process.env[key]
    else process.env[key] = value
  }
  vi.resetModules()
})

describe("Playwright live deployment mode", () => {
  it("requires a target URL when live deployment mode is enabled", async () => {
    await expect(loadConfig({ E2E_LIVE_DEPLOYMENT: "1" })).rejects.toThrow(
      "E2E_BASE_URL must be set when E2E_LIVE_DEPLOYMENT=1",
    )
  })

  it("uses the configured live target without starting loopback services", async () => {
    const config = await loadConfig({
      E2E_LIVE_DEPLOYMENT: "1",
      E2E_BASE_URL: "https://adas.local",
    })

    expect(config.use?.baseURL).toBe("https://adas.local")
    expect(config.use?.ignoreHTTPSErrors).not.toBe(true)
    expect(config.webServer).toEqual([])
  })
})
