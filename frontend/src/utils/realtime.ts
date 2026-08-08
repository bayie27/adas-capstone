import type { AlertStatus } from "@/types/alerts"
import type { CameraAiStatus, CameraConnectionStatus } from "@/types/cameras"
import type {
  RealtimeAlertEventType,
  RealtimeAlertPayload,
  RealtimeCameraStatusPayload,
} from "@/types/realtime"

const ALERT_EVENT_TYPES: RealtimeAlertEventType[] = ["NEW_DETECTION", "NEW_ALERT", "NEW_ACCIDENT"]
const ALERT_STATUS_VALUES: AlertStatus[] = ["Unverified", "Ongoing", "Dismissed", "Resolved"]
const CAMERA_CONNECTION_STATUS_VALUES: CameraConnectionStatus[] = [
  "Connected",
  "Disconnected",
  "Reconnecting",
  "Unresponsive",
]
const CAMERA_AI_STATUS_VALUES: CameraAiStatus[] = ["Active", "Inactive", "Paused", "Unresponsive"]

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object"
}

function isAlertEventType(value: unknown): value is RealtimeAlertEventType {
  return typeof value === "string" && ALERT_EVENT_TYPES.includes(value as RealtimeAlertEventType)
}

function isAlertStatus(value: unknown): value is AlertStatus {
  return typeof value === "string" && ALERT_STATUS_VALUES.includes(value as AlertStatus)
}

function isCameraConnectionStatus(value: unknown): value is CameraConnectionStatus {
  return (
    typeof value === "string" &&
    CAMERA_CONNECTION_STATUS_VALUES.includes(value as CameraConnectionStatus)
  )
}

function isCameraAiStatus(value: unknown): value is CameraAiStatus {
  return typeof value === "string" && CAMERA_AI_STATUS_VALUES.includes(value as CameraAiStatus)
}

function getAlertCandidate(payload: Record<string, unknown>) {
  if (isRecord(payload.alert)) {
    return payload.alert
  }

  if (isRecord(payload.data)) {
    return payload.data
  }

  return payload
}

export function normalizeRealtimeAlert(payload: unknown): RealtimeAlertPayload | null {
  if (!isRecord(payload) || !isAlertEventType(payload.type)) {
    return null
  }

  const alert = getAlertCandidate(payload)

  if (
    typeof alert.log_id !== "number" ||
    typeof alert.camera_id !== "number" ||
    typeof alert.detected_at !== "string" ||
    typeof alert.snapshot_path !== "string" ||
    typeof alert.confidence_score !== "number" ||
    !isAlertStatus(alert.detection_status)
  ) {
    return null
  }

  return {
    type: payload.type,
    log_id: alert.log_id,
    camera_id: alert.camera_id,
    detected_at: alert.detected_at,
    snapshot_path: alert.snapshot_path,
    confidence_score: alert.confidence_score,
    detection_status: alert.detection_status,
    camera_name: typeof alert.camera_name === "string" ? alert.camera_name : null,
  }
}

export function normalizeRealtimeCameraStatus(
  payload: unknown,
): RealtimeCameraStatusPayload | null {
  if (!isRecord(payload) || payload.type !== "CAMERA_STATUS_UPDATE") {
    return null
  }

  if (
    typeof payload.camera_id !== "number" ||
    !isCameraConnectionStatus(payload.connection_status) ||
    !isCameraAiStatus(payload.ai_status)
  ) {
    return null
  }

  return {
    type: "CAMERA_STATUS_UPDATE",
    camera_id: payload.camera_id,
    connection_status: payload.connection_status,
    ai_status: payload.ai_status,
  }
}
