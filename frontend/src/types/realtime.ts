import type { AlertStatus } from "@/types/alerts"
import type { CameraAiStatus, CameraConnectionStatus } from "@/types/cameras"

export type RealtimeEventType =
  | "CONNECTION_READY"
  | "NEW_DETECTION"
  | "ALERT_STATUS_UPDATE"
  | "CAMERA_STATUS_UPDATE"
  | "SNOOZE_ACTIVATED"
  | "RE_ALARM"

// 01_CONTRACTS.md §9.1 — every server message is wrapped in this envelope.
export interface EventEnvelope {
  version: 1
  event_id: string
  type: RealtimeEventType
  occurred_at: string
  data: Record<string, unknown>
}

export interface ConnectionReadyData {
  connection_id: string
  server_time: string
  user_id: number
  role: string
}

// 01_CONTRACTS.md §9.3 — carried by NEW_DETECTION, and as the base of
// ALERT_STATUS_UPDATE. `snapshot_url` points at the P4 authenticated
// snapshot route, which does not exist on the backend yet — do not render
// it directly, see RealtimeAlertsBridge's enrichment fetch.
export interface IncidentPayload {
  log_id: number
  source_event_id: string
  camera_id: number
  camera_name: string | null
  detected_at: string
  confidence_score: number
  detection_status: AlertStatus
  snapshot_url: string
  verified_by_id: number | null
  verified_by_name: string | null
  verified_at: string | null
  closed_by_id: number | null
  closed_by_name: string | null
  closed_at: string | null
  snoozed_until: string | null
  snoozed_by_id: number | null
  created_at: string
  updated_at: string
}

export interface AlertStatusUpdateData extends IncidentPayload {
  action: string
  handled_by: string | null
  handled_at: string | null
}

export interface CameraStatusUpdateData {
  camera_id: number
  camera_name: string
  is_enabled: boolean
  desired_ai_state: string
  desired_state_reason: string | null
  connection_status: CameraConnectionStatus
  ai_status: CameraAiStatus
  cooldown_until: string | null
  config_version: number
}

export interface SnoozeActivatedData {
  log_id: number
  camera_id: number
  snoozed_by: number | null
  snoozed_until: string
}

export interface ReAlarmData {
  log_id: number
  camera_id: number
}
