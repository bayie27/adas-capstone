import type { AlertStatus } from "@/types/alerts"
import type { CameraAiStatus, CameraConnectionStatus } from "@/types/cameras"

export type RealtimeAlertEventType = "NEW_DETECTION" | "NEW_ALERT" | "NEW_ACCIDENT"

export interface RealtimeAlertPayload {
  type: RealtimeAlertEventType
  log_id: number
  camera_id: number
  detected_at: string
  snapshot_path: string
  confidence_score: number
  detection_status: AlertStatus
  camera_name?: string | null
}

export interface RealtimeCameraStatusPayload {
  type: "CAMERA_STATUS_UPDATE"
  camera_id: number
  connection_status: CameraConnectionStatus
  ai_status: CameraAiStatus
}
