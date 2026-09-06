import { describe, expect, it } from "vitest"

import {
  describeCameraDesiredState,
  describeSnoozeStatus,
  formatFileSize,
  isCameraDetectionDisabled,
  isCameraInCooldown,
} from "@/utils/format"

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

describe("isCameraDetectionDisabled", () => {
  it("is true only for the disabled reason", () => {
    expect(isCameraDetectionDisabled(camera("disabled"))).toBe(true)
    expect(isCameraDetectionDisabled(camera("incident"))).toBe(false)
    expect(isCameraDetectionDisabled(camera("cooldown"))).toBe(false)
    expect(isCameraDetectionDisabled(camera(null))).toBe(false)
  })
})

describe("describeSnoozeStatus", () => {
  it("says nothing when there is no active snooze", () => {
    expect(describeSnoozeStatus(null, NOW, null, null)).toBeNull()
  })

  it("leads with when the snooze started, not just when it resumes", () => {
    expect(describeSnoozeStatus("2026-08-14T12:05:00Z", NOW, null, "2026-08-14T11:58:00Z")).toMatch(
      /^Muted at \d{2}:\d{2} — resumes in 300s$/,
    )
  })

  it("falls back to the un-prefixed form when snoozed_at is missing", () => {
    expect(describeSnoozeStatus("2026-08-14T12:05:00Z", NOW, null, null)).toBe(
      "Muted — resumes in 300s",
    )
  })

  it("still names who snoozed it alongside the start time", () => {
    expect(
      describeSnoozeStatus("2026-08-14T12:05:00Z", NOW, "Jane Doe", "2026-08-14T11:58:00Z"),
    ).toMatch(/^Muted at \d{2}:\d{2} by Jane Doe — resumes in 300s$/)
  })
})

describe("formatFileSize", () => {
  it("renders bytes, KB, MB and GB at their natural boundaries", () => {
    expect(formatFileSize(512)).toBe("512 B")
    expect(formatFileSize(2048)).toBe("2.0 KB")
    expect(formatFileSize(5 * 1024 * 1024)).toBe("5.0 MB")
    expect(formatFileSize(3 * 1024 * 1024 * 1024)).toBe("3.00 GB")
  })
})
