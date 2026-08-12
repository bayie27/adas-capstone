import { describe, expect, it } from "vitest"

import { shouldApplyCameraEvent, shouldApplyIncidentEvent } from "./merge"

const T0 = "2026-08-13T10:00:00Z"
const T1 = "2026-08-13T10:00:01Z"

describe("shouldApplyIncidentEvent", () => {
  it("drops an event older than the incident already held", () => {
    expect(shouldApplyIncidentEvent(T0, T1)).toBe(false)
  })

  it("applies an event with the same key", () => {
    expect(shouldApplyIncidentEvent(T0, T0)).toBe(true)
  })

  it("applies an event newer than the incident already held", () => {
    expect(shouldApplyIncidentEvent(T1, T0)).toBe(true)
  })

  it("applies an event with no key of its own", () => {
    expect(shouldApplyIncidentEvent(undefined, T1)).toBe(true)
    expect(shouldApplyIncidentEvent(null, T1)).toBe(true)
    expect(shouldApplyIncidentEvent("", T1)).toBe(true)
  })

  it("applies an event when nothing is held to compare against", () => {
    expect(shouldApplyIncidentEvent(T0, undefined)).toBe(true)
    expect(shouldApplyIncidentEvent(T0, null)).toBe(true)
  })

  it("applies an event when either key is unparsable", () => {
    expect(shouldApplyIncidentEvent("not-a-date", T1)).toBe(true)
    expect(shouldApplyIncidentEvent(T0, "not-a-date")).toBe(true)
  })

  it("compares instants, not strings, across offsets", () => {
    // 10:00:00Z is one second newer than 11:00:59+01:00 (10:00:59Z is later,
    // so this must be the drop direction) — a lexical compare gets it wrong.
    expect(shouldApplyIncidentEvent("2026-08-13T10:00:00Z", "2026-08-13T11:00:59+01:00")).toBe(
      false,
    )
    expect(shouldApplyIncidentEvent("2026-08-13T11:00:59+01:00", "2026-08-13T10:00:00Z")).toBe(true)
  })

  it("respects sub-second precision", () => {
    expect(shouldApplyIncidentEvent("2026-08-13T10:00:00.100Z", "2026-08-13T10:00:00.200Z")).toBe(
      false,
    )
    expect(shouldApplyIncidentEvent("2026-08-13T10:00:00.200Z", "2026-08-13T10:00:00.100Z")).toBe(
      true,
    )
  })
})

describe("shouldApplyCameraEvent", () => {
  it("drops an event older than the camera already held", () => {
    expect(shouldApplyCameraEvent(4, 5)).toBe(false)
  })

  it("applies an event with the same version", () => {
    expect(shouldApplyCameraEvent(5, 5)).toBe(true)
  })

  it("applies an event newer than the camera already held", () => {
    expect(shouldApplyCameraEvent(6, 5)).toBe(true)
  })

  it("applies an event with no version of its own", () => {
    expect(shouldApplyCameraEvent(undefined, 5)).toBe(true)
    expect(shouldApplyCameraEvent(null, 5)).toBe(true)
  })

  it("applies an event when nothing is held to compare against", () => {
    expect(shouldApplyCameraEvent(5, undefined)).toBe(true)
    expect(shouldApplyCameraEvent(5, null)).toBe(true)
  })

  it("applies an event when either version is not a finite number", () => {
    expect(shouldApplyCameraEvent(Number.NaN, 5)).toBe(true)
    expect(shouldApplyCameraEvent(5, Number.NaN)).toBe(true)
  })

  it("treats version 0 as a real version, not as absent", () => {
    expect(shouldApplyCameraEvent(0, 1)).toBe(false)
    expect(shouldApplyCameraEvent(1, 0)).toBe(true)
    expect(shouldApplyCameraEvent(0, 0)).toBe(true)
  })
})
