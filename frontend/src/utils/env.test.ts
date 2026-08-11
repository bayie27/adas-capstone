import { describe, expect, it, vi } from "vitest"
import { getBrowserHostname, getBrowserProtocol, trimTrailingSlash } from "./env"

describe("trimTrailingSlash", () => {
  it("removes a single trailing slash", () => {
    expect(trimTrailingSlash("http://localhost:8000/")).toBe("http://localhost:8000")
  })

  it("removes multiple trailing slashes", () => {
    expect(trimTrailingSlash("http://localhost:8000///")).toBe("http://localhost:8000")
  })

  it("leaves a value with no trailing slash unchanged", () => {
    expect(trimTrailingSlash("http://localhost:8000")).toBe("http://localhost:8000")
  })
})

describe("getBrowserHostname", () => {
  it("returns window.location.hostname when set", () => {
    expect(getBrowserHostname()).toBe(window.location.hostname)
  })

  it("falls back to localhost when hostname is empty", () => {
    const spy = vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      hostname: "",
    })

    expect(getBrowserHostname()).toBe("localhost")

    spy.mockRestore()
  })
})

describe("getBrowserProtocol", () => {
  it("returns window.location.protocol when set", () => {
    expect(getBrowserProtocol()).toBe(window.location.protocol)
  })

  it("returns https: under TLS so WS_BASE_URL derives wss:", () => {
    const spy = vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      protocol: "https:",
    })

    expect(getBrowserProtocol()).toBe("https:")

    spy.mockRestore()
  })

  it("falls back to http: when protocol is empty", () => {
    const spy = vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      protocol: "",
    })

    expect(getBrowserProtocol()).toBe("http:")

    spy.mockRestore()
  })
})
