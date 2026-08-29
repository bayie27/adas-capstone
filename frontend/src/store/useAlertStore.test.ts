import { beforeEach, describe, expect, it, vi } from "vitest"
import { useAlertStore } from "./useAlertStore"
import type { AlertLog } from "@/api/alerts"
import * as soundModule from "@/utils/detectionSound"

vi.mock("@/utils/detectionSound", () => ({
  playDetectionSound: vi.fn(),
  stopDetectionSound: vi.fn(),
}))

const mockUnverifiedAlert: AlertLog = {
  log_id: 1,
  source_event_id: "evt-1",
  camera_id: 1,
  detected_at: "2026-08-27T10:00:00Z",
  confidence_score: 0.9,
  detection_status: "Unverified",
  snapshot_url: "https://example.com/1.jpg",
  verified_by_id: null,
  verified_by_name: null,
  verified_at: null,
  closed_by_id: null,
  closed_by_name: null,
  closed_at: null,
  snoozed_at: null,
  snoozed_until: null,
  snoozed_by_id: null,
  camera_name: "Camera 1",
  created_at: "2026-08-27T10:00:00Z",
  updated_at: "2026-08-27T10:00:00Z",
}

const mockOngoingAlert: AlertLog = {
  ...mockUnverifiedAlert,
  log_id: 2,
  detection_status: "Ongoing",
  verified_by_name: "Operator A",
  verified_at: "2026-08-27T10:01:00Z",
}

describe("useAlertStore", () => {
  beforeEach(() => {
    useAlertStore.getState().clearAlerts()
    vi.clearAllMocks()
  })

  it("triggers playDetectionSound when an Unverified alert is added", () => {
    useAlertStore.getState().addAlert(mockUnverifiedAlert)
    expect(soundModule.playDetectionSound).toHaveBeenCalledTimes(1)
    expect(soundModule.stopDetectionSound).not.toHaveBeenCalled()
  })

  it("does NOT trigger playDetectionSound when an Ongoing alert is added", () => {
    useAlertStore.getState().addAlert(mockOngoingAlert)
    expect(soundModule.playDetectionSound).not.toHaveBeenCalled()
    expect(useAlertStore.getState().alerts).toHaveLength(1)
    expect(useAlertStore.getState().alerts[0].detection_status).toBe("Ongoing")
  })

  it("stops detection sound when an Unverified alert is updated to Ongoing", () => {
    useAlertStore.getState().addAlert(mockUnverifiedAlert)
    expect(soundModule.playDetectionSound).toHaveBeenCalledTimes(1)

    // Move to Ongoing
    useAlertStore.getState().addAlert({
      ...mockUnverifiedAlert,
      detection_status: "Ongoing",
      updated_at: "2026-08-27T10:02:00Z",
    })

    expect(soundModule.stopDetectionSound).toHaveBeenCalledTimes(1)
    expect(useAlertStore.getState().alerts[0].detection_status).toBe("Ongoing")
  })

  it("stops detection sound when Unverified alert is removed or snoozed", () => {
    useAlertStore.getState().addAlert(mockUnverifiedAlert)
    expect(soundModule.playDetectionSound).toHaveBeenCalledTimes(1)

    useAlertStore.getState().removeAlert(mockUnverifiedAlert.log_id)
    expect(soundModule.stopDetectionSound).toHaveBeenCalledTimes(1)
  })

  it("automatically re-alarms when snooze duration expires", () => {
    vi.useFakeTimers()
    try {
      useAlertStore.getState().addAlert(mockUnverifiedAlert)
      expect(soundModule.playDetectionSound).toHaveBeenCalledTimes(1)

      // Snooze for 10 seconds
      const futureDate = new Date(Date.now() + 10_000).toISOString()
      useAlertStore.getState().activateSnooze(mockUnverifiedAlert.log_id, futureDate, "Operator A")

      // Sound should stop while snoozed
      expect(soundModule.stopDetectionSound).toHaveBeenCalledTimes(1)

      // Advance clock by 10.1 seconds
      vi.advanceTimersByTime(10_100)

      // Sound should play again (re-alarmed)
      expect(soundModule.playDetectionSound).toHaveBeenCalledTimes(2)
      expect(useAlertStore.getState().snoozedUntil[mockUnverifiedAlert.log_id]).toBeUndefined()
    } finally {
      vi.useRealTimers()
    }
  })

  it("plays alarm when a new alert arrives while existing alerts are snoozed", () => {
    const alert1 = { ...mockUnverifiedAlert, log_id: 101 }
    const alert2 = { ...mockUnverifiedAlert, log_id: 102 }
    const alert3 = { ...mockUnverifiedAlert, log_id: 103 }

    // Add alert 1 & 2
    useAlertStore.getState().addAlert(alert1)
    useAlertStore.getState().addAlert(alert2)
    expect(soundModule.playDetectionSound).toHaveBeenCalledTimes(1)

    // Snooze both alert 1 & 2
    const futureDate = new Date(Date.now() + 60_000).toISOString()
    useAlertStore.getState().activateSnooze(101, futureDate, "Operator")
    // Still 1 unsnoozed alert (102), so sound has not stopped yet
    expect(soundModule.stopDetectionSound).not.toHaveBeenCalled()

    useAlertStore.getState().activateSnooze(102, futureDate, "Operator")
    // Now all alerts snoozed, sound stops
    expect(soundModule.stopDetectionSound).toHaveBeenCalledTimes(1)

    // Alert 3 arrives (fresh/unsnoozed) -> alarm sounds again!
    useAlertStore.getState().addAlert(alert3)
    expect(soundModule.playDetectionSound).toHaveBeenCalledTimes(2)

    // Snooze alert 3 -> alarm stops again
    useAlertStore.getState().activateSnooze(103, futureDate, "Operator")
    expect(soundModule.stopDetectionSound).toHaveBeenCalledTimes(2)
  })
})
