import { describe, expect, it } from "vitest"

import { describeCameraDesiredState, isCameraInCooldown } from "@/utils/format"

const NOW = Date.parse("2026-08-14T12:00:00Z")

function camera(desired_state_reason: string | null, cooldown_until: string | null = null) {
  return { desired_state_reason, cooldown_until }
}

describe("describeCameraDesiredState", () => {
  it("says nothing for a camera in its normal state", () => {
    expect(describeCameraDesiredState(camera(null), NOW)).toBeNull()
  })

  it("distinguishes the three reasons a camera is not detecting", () => {
    const disabled = describeCameraDesiredState(camera("disabled"), NOW)
    const incident = describeCameraDesiredState(camera("incident"), NOW)
    const cooldown = describeCameraDesiredState(camera("cooldown", "2026-08-14T12:00:42Z"), NOW)

    expect(disabled).toBeTruthy()
    expect(incident).toBeTruthy()
    expect(cooldown).toBeTruthy()
    // The whole point: three states that used to read identically must not
    // collapse back into one another.
    expect(new Set([disabled, incident, cooldown]).size).toBe(3)
  })

  it("counts a cooldown down to its deadline", () => {
    expect(describeCameraDesiredState(camera("cooldown", "2026-08-14T12:00:42Z"), NOW)).toContain(
      "42s",
    )
  })

  it("does not count past the deadline", () => {
    expect(describeCameraDesiredState(camera("cooldown", "2026-08-14T11:59:00Z"), NOW)).toBe(
      "Dismissal cooldown — resuming",
    )
  })

  it("falls back when the deadline is missing or unparsable", () => {
    expect(describeCameraDesiredState(camera("cooldown", null), NOW)).toBe("Dismissal cooldown")
    expect(describeCameraDesiredState(camera("cooldown", "not-a-date"), NOW)).toBe(
      "Dismissal cooldown",
    )
  })

  it("stays quiet on a reason this build does not know", () => {
    expect(describeCameraDesiredState(camera("some-future-reason"), NOW)).toBeNull()
  })
})

describe("isCameraInCooldown", () => {
  it("is true only for the cooldown reason", () => {
    expect(isCameraInCooldown(camera("cooldown"))).toBe(true)
    expect(isCameraInCooldown(camera("incident"))).toBe(false)
    expect(isCameraInCooldown(camera(null))).toBe(false)
  })
})
