import { afterEach, describe, expect, it, vi } from "vitest"

import { getMfaRateLimitDeadline, MFA_RATE_LIMIT_FALLBACK_SECONDS } from "./mfaUi"
import { setServerClockOffsetMs } from "@/utils/datetime"

function rateLimitError(retryAfter?: string) {
  return Object.assign(new Error("Request failed"), {
    isAxiosError: true,
    response: {
      status: 429,
      data: { code: "AUTH_RATE_LIMITED" },
      headers: retryAfter === undefined ? {} : { "retry-after": retryAfter },
    },
  })
}

describe("MFA rate-limit fallback", () => {
  afterEach(() => {
    setServerClockOffsetMs(0)
    vi.useRealTimers()
  })

  it.each([undefined, "invalid", "0", "-5"])(
    "uses the safe fallback when Retry-After is absent or invalid (%s)",
    (retryAfter) => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date("2026-10-18T12:00:00Z"))

      const deadline = getMfaRateLimitDeadline(rateLimitError(retryAfter))

      expect(deadline).toBe(
        new Date(Date.now() + MFA_RATE_LIMIT_FALLBACK_SECONDS * 1000).toISOString(),
      )
    },
  )

  it("uses a valid Retry-After value from the server", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-10-18T12:00:00Z"))

    expect(getMfaRateLimitDeadline(rateLimitError("45"))).toBe(
      new Date(Date.now() + 45_000).toISOString(),
    )
  })
})
