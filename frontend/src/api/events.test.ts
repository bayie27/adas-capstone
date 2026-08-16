import { describe, expect, it } from "vitest"

import { asMaintenanceNoticeData, asSnoozeActivatedData, parseEventEnvelope } from "@/api/events"

// MAINTENANCE_NOTICE was absent from three places at once: the
// RealtimeEventType union, the EVENT_TYPES runtime array backing
// isEventType(), and its own narrower. Missing (2) is the live bug — the
// envelope is discarded by parseEventEnvelope before any switch sees it,
// so a handler wired up without it would never run and a test that fakes
// the envelope would pass anyway. These cover the real path end to end.

function envelope(type: unknown, data: Record<string, unknown>) {
  return {
    version: 1,
    event_id: "11111111-1111-1111-1111-111111111111",
    type,
    occurred_at: "2026-08-15T12:00:00Z",
    data,
  }
}

describe("parseEventEnvelope — MAINTENANCE_NOTICE", () => {
  it("accepts the envelope now that the type is in the runtime allowlist", () => {
    const parsed = parseEventEnvelope(
      envelope("MAINTENANCE_NOTICE", { message: "Restoring soon.", backup_id: "backup-1" }),
    )

    expect(parsed).not.toBeNull()
    expect(parsed?.type).toBe("MAINTENANCE_NOTICE")
  })

  it("still rejects a type absent from the allowlist", () => {
    expect(parseEventEnvelope(envelope("SOMETHING_UNKNOWN", { message: "x" }))).toBeNull()
  })
})

describe("asMaintenanceNoticeData", () => {
  it("parses a real restore notice", () => {
    expect(
      asMaintenanceNoticeData({
        message: "A restore is about to take the backend offline.",
        backup_id: "backup-42",
      }),
    ).toEqual({
      message: "A restore is about to take the backend offline.",
      backup_id: "backup-42",
    })
  })

  it("accepts a null backup_id — the dev-reseed producer has no backup to name", () => {
    expect(
      asMaintenanceNoticeData({ message: "The database was reseeded.", backup_id: null }),
    ).toEqual({ message: "The database was reseeded.", backup_id: null })
  })

  it("rejects a missing message", () => {
    expect(asMaintenanceNoticeData({ backup_id: null })).toBeNull()
  })

  it("rejects a backup_id that is present but not a string or null", () => {
    expect(asMaintenanceNoticeData({ message: "x", backup_id: 42 })).toBeNull()
  })
})

// P21 Step 3 (breaking): snoozed_by went from an id an Operator had no way
// to resolve (GET /api/users/ is admin-only) to a formatted display name
// sent to every role. The validator originally shipped checking a number
// and silently discarded every real envelope after the backend changed —
// this is the regression guard against that ever happening again.
describe("asSnoozeActivatedData", () => {
  it("accepts a real envelope carrying the formatted name P21 actually sends", () => {
    expect(
      asSnoozeActivatedData({
        log_id: 42,
        camera_id: 3,
        snoozed_by: "Jane Doe",
        snoozed_until: "2026-08-17T00:05:00Z",
      }),
    ).toEqual({
      log_id: 42,
      camera_id: 3,
      snoozed_by: "Jane Doe",
      snoozed_until: "2026-08-17T00:05:00Z",
    })
  })

  it("accepts a null snoozed_by — the snoozing user has since been deleted", () => {
    expect(
      asSnoozeActivatedData({
        log_id: 42,
        camera_id: 3,
        snoozed_by: null,
        snoozed_until: "2026-08-17T00:05:00Z",
      }),
    ).toEqual({ log_id: 42, camera_id: 3, snoozed_by: null, snoozed_until: "2026-08-17T00:05:00Z" })
  })

  it("rejects the old pre-P21 shape — a numeric snoozed_by is no longer valid", () => {
    expect(
      asSnoozeActivatedData({
        log_id: 42,
        camera_id: 3,
        snoozed_by: 7,
        snoozed_until: "2026-08-17T00:05:00Z",
      }),
    ).toBeNull()
  })
})
