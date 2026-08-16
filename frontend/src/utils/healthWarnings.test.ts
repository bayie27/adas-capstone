import { describe, expect, it } from "vitest"

import { describeWarning, humanizeWarningCode } from "@/utils/healthWarnings"

function warning(
  code: string,
  severity: string,
  measurement: number | null,
  threshold: number | null,
) {
  return { code, severity, measurement, threshold }
}

describe("describeWarning", () => {
  it("renders each of the five known codes with a real sentence", () => {
    expect(describeWarning(warning("GPU_TEMP_CRITICAL", "critical", 88, 85)).message).toContain(
      "88",
    )
    expect(describeWarning(warning("RAM_CRITICAL", "critical", 96, 95)).tone).toBe("danger")
    expect(describeWarning(warning("DISK_CRITICAL", "critical", 92, 90)).tone).toBe("danger")
    expect(describeWarning(warning("DISK_WARNING", "warning", 82, 80)).tone).toBe("warning")
  })

  // The one behaviour no backend test can cover: measurement is a literal 0
  // meaning "no camera reported", not a rate — it must never be printed as
  // one of the other codes' numeric sentences would.
  it("never renders AI_HEARTBEAT_STALE's literal 0 measurement as a rate", () => {
    const described = describeWarning(warning("AI_HEARTBEAT_STALE", "warning", 0, 10))
    expect(described.message).not.toMatch(/^0/)
    expect(described.message).toContain("AI engine")
    expect(described.message).toContain("10")
  })

  // The open-fallback rule: a code the client has never seen must render its
  // severity tone and its numbers rather than disappearing or throwing.
  it("renders an unrecognised code via the fallback instead of dropping it", () => {
    const described = describeWarning(warning("SOMETHING_NEW", "critical", 42, 10))
    expect(described.tone).toBe("danger")
    expect(described.message).toContain("42")
    expect(described.message).toContain("10")
    expect(described.label).toBe("Something New")
  })

  it("falls back to the humanised code alone when there are no numbers", () => {
    expect(describeWarning(warning("SOMETHING_NEW", "warning", null, null)).message).toBe(
      "Something New",
    )
  })

  it("defaults an unrecognised severity to a neutral tone rather than throwing", () => {
    expect(describeWarning(warning("SOMETHING_NEW", "unknown-severity", 1, 2)).tone).toBe("neutral")
  })

  it("humanises an arbitrary SCREAMING_SNAKE_CASE code into Title Case", () => {
    expect(humanizeWarningCode("SOME_FUTURE_CODE")).toBe("Some Future Code")
  })
})
