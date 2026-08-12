import { beforeEach, describe, expect, it, vi } from "vitest"

/**
 * These assert the request PATHS, not behaviour, and they exist because a
 * real bug got all the way to a running browser: every function here was
 * written as "/api/dev/...", but the shared axios instance's baseURL already
 * ends in "/api" (utils/env.ts), so every call resolved to /api/api/dev/...
 * and 404'd. The dev panel silently never appeared, because its gate is the
 * probe succeeding.
 *
 * The component tests could not catch it — they mock "@/services/dev"
 * wholesale, so no real URL is ever constructed. These mock the axios
 * instance one level down instead.
 */

vi.mock("@/services/api", () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

const api = (await import("@/services/api")).default
const dev = await import("./dev")

describe("dev service request paths", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockClear()
    vi.mocked(api.post).mockClear()
  })

  it("does not re-prefix /api, which baseURL already provides", async () => {
    await dev.getDevStatus()
    await dev.reseedProfile("demo")
    await dev.loginAs("admin")
    await dev.injectDetection({})
    await dev.setCameraState(1, { stale_heartbeat: true })
    await dev.generateHealthHistory(7)

    const paths = [
      ...vi.mocked(api.get).mock.calls.map((call) => call[0]),
      ...vi.mocked(api.post).mock.calls.map((call) => call[0]),
    ]

    expect(paths).toHaveLength(6)
    for (const path of paths) {
      expect(path).not.toMatch(/^\/api\//)
      expect(path).toMatch(/^\/dev\//)
    }
  })

  it("targets the documented endpoints", async () => {
    await dev.getDevStatus()
    expect(api.get).toHaveBeenCalledWith("/dev/status")

    await dev.reseedProfile("demo", "dsahagun")
    expect(api.post).toHaveBeenCalledWith("/dev/reseed", {
      profile: "demo",
      login_as: "dsahagun",
    })

    // login_as is omitted entirely when not given, so the backend applies
    // its own "caller's username, falling back to admin" default.
    await dev.reseedProfile("empty")
    expect(api.post).toHaveBeenCalledWith("/dev/reseed", { profile: "empty" })

    await dev.setCameraState(42, { clear_cooldown: true })
    expect(api.post).toHaveBeenCalledWith("/dev/cameras/42/state", {
      clear_cooldown: true,
    })
  })
})
