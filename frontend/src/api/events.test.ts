import { describe, expect, it } from "vitest"

import { asMaintenanceNoticeData, parseEventEnvelope } from "@/api/events"

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
