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
})
