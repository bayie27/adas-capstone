import { describe, expect, it } from "vitest"

import {
  computeClockOffsetMs,
  correctedNowMs,
  getServerClockOffsetMs,
  setServerClockOffsetMs,
} from "@/utils/datetime"

// A sign error here makes every relative timestamp in the product wrong in
// the same direction — the exact failure the phase's own risk note calls
// out as "looks plausible and gets shipped." Covering ahead, behind, equal
// and missing is what the risk note asks for explicitly.
describe("computeClockOffsetMs", () => {
  const browserNowMs = Date.parse("2026-08-16T12:00:00Z")

  it("is negative when the browser clock is ahead of the server", () => {
    const serverTime = "2026-08-16T11:50:00Z" // 10 minutes behind the browser
    expect(computeClockOffsetMs(serverTime, browserNowMs)).toBe(-10 * 60_000)
  })

  it("is positive when the browser clock is behind the server", () => {
    const serverTime = "2026-08-16T12:10:00Z" // 10 minutes ahead of the browser
    expect(computeClockOffsetMs(serverTime, browserNowMs)).toBe(10 * 60_000)
  })

  it("is zero when the clocks agree", () => {
    expect(computeClockOffsetMs("2026-08-16T12:00:00Z", browserNowMs)).toBe(0)
  })

  it("falls back to 0, not NaN, when server_time is missing", () => {
    expect(computeClockOffsetMs(null, browserNowMs)).toBe(0)
    expect(computeClockOffsetMs(undefined, browserNowMs)).toBe(0)
  })

  it("falls back to 0, not NaN, when server_time is unparseable", () => {
    expect(computeClockOffsetMs("not-a-date", browserNowMs)).toBe(0)
  })
})

describe("correctedNowMs", () => {
  it("applies the last offset set", () => {
    setServerClockOffsetMs(5 * 60_000)
    expect(getServerClockOffsetMs()).toBe(5 * 60_000)
    expect(correctedNowMs() - Date.now()).toBeCloseTo(5 * 60_000, -2)
    setServerClockOffsetMs(0)
  })
})
