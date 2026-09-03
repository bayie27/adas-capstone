import type { AlertStatus } from "@/api/alerts"
import type { CameraAiStatus, CameraConnectionStatus } from "@/api/cameras"

export type RealtimeEventType =
  | "CONNECTION_READY"
  | "NEW_DETECTION"
  | "ALERT_STATUS_UPDATE"
  | "CAMERA_STATUS_UPDATE"
  | "SNOOZE_ACTIVATED"
  | "RE_ALARM"
  | "MAINTENANCE_NOTICE"

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
// ALERT_STATUS_UPDATE. `snapshot_url` is the P4 authenticated snapshot
// route (e.g. `/api/alerts/42/snapshot`) — pass it straight to SnapshotImage.
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

/**
 * `snoozed_by` is the formatted display name (`format_user_name`,
 * `services/events.py:87`), not an id — P21 Step 3, breaking. It was
 * previously an id an Operator had no way to resolve, since `GET /api/users/`
 * is admin-only; that constraint no longer applies, since every role now
 * receives the name directly. `null` still means "unknown" (the snoozing
 * user was deleted).
 */
export interface SnoozeActivatedData {
  log_id: number
  camera_id: number
  snoozed_by: string | null
  snoozed_until: string
}

export interface ReAlarmData {
  log_id: number
  camera_id: number
}

// Broadcast just before `POST /api/system/restores` takes the backend
// offline (best-effort — a broadcast failure never fails that request, so
// this may legitimately never arrive), and by a dev-tools reseed, which has
// no backup to name — hence `backup_id` being nullable rather than every
// producer inventing a placeholder.
export interface MaintenanceNoticeData {
  message: string
  backup_id: string | null
}

const EVENT_TYPES: RealtimeEventType[] = [
  "CONNECTION_READY",
  "NEW_DETECTION",
  "ALERT_STATUS_UPDATE",
  "CAMERA_STATUS_UPDATE",
  "SNOOZE_ACTIVATED",
  "RE_ALARM",
  "MAINTENANCE_NOTICE",
]
const ALERT_STATUS_VALUES: AlertStatus[] = ["Unverified", "Ongoing", "Dismissed", "Cleared"]
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

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string"
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === "number"
}

function isEventType(value: unknown): value is RealtimeEventType {
  return typeof value === "string" && EVENT_TYPES.includes(value as RealtimeEventType)
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

// 01_CONTRACTS.md §9.1 — the envelope every server message is wrapped in.
export function parseEventEnvelope(raw: unknown): EventEnvelope | null {
  if (
    !isRecord(raw) ||
    raw.version !== 1 ||
    typeof raw.event_id !== "string" ||
    !isEventType(raw.type) ||
    typeof raw.occurred_at !== "string" ||
    !isRecord(raw.data)
  ) {
    return null
  }

  return {
    version: 1,
    event_id: raw.event_id,
    type: raw.type,
    occurred_at: raw.occurred_at,
    data: raw.data,
  }
}

export function asConnectionReadyData(data: Record<string, unknown>): ConnectionReadyData | null {
  if (
    typeof data.connection_id !== "string" ||
    typeof data.server_time !== "string" ||
    typeof data.user_id !== "number" ||
    typeof data.role !== "string"
  ) {
    return null
  }

  return {
    connection_id: data.connection_id,
    server_time: data.server_time,
    user_id: data.user_id,
    role: data.role,
  }
}

// Shared by NEW_DETECTION and ALERT_STATUS_UPDATE — the latter's data is a
// superset (adds action/handled_by/handled_at), so validating the common
// incident fields covers both.
export function asIncidentPayload(data: Record<string, unknown>): IncidentPayload | null {
  if (
    typeof data.log_id !== "number" ||
    typeof data.source_event_id !== "string" ||
    typeof data.camera_id !== "number" ||
    !isNullableString(data.camera_name) ||
    typeof data.detected_at !== "string" ||
    typeof data.confidence_score !== "number" ||
    !isAlertStatus(data.detection_status) ||
    typeof data.snapshot_url !== "string" ||
    !isNullableNumber(data.verified_by_id) ||
    !isNullableString(data.verified_by_name) ||
    !isNullableString(data.verified_at) ||
    !isNullableNumber(data.closed_by_id) ||
    !isNullableString(data.closed_by_name) ||
    !isNullableString(data.closed_at) ||
    !isNullableString(data.snoozed_until) ||
    !isNullableNumber(data.snoozed_by_id) ||
    typeof data.created_at !== "string" ||
    typeof data.updated_at !== "string"
  ) {
    return null
  }

  return {
    log_id: data.log_id,
    source_event_id: data.source_event_id,
    camera_id: data.camera_id,
    camera_name: data.camera_name,
    detected_at: data.detected_at,
    confidence_score: data.confidence_score,
    detection_status: data.detection_status,
    snapshot_url: data.snapshot_url,
    verified_by_id: data.verified_by_id,
    verified_by_name: data.verified_by_name,
    verified_at: data.verified_at,
    closed_by_id: data.closed_by_id,
    closed_by_name: data.closed_by_name,
    closed_at: data.closed_at,
    snoozed_until: data.snoozed_until,
    snoozed_by_id: data.snoozed_by_id,
    created_at: data.created_at,
    updated_at: data.updated_at,
  }
}

export function asAlertStatusUpdateData(
  data: Record<string, unknown>,
): AlertStatusUpdateData | null {
  const incident = asIncidentPayload(data)

  if (
    !incident ||
    typeof data.action !== "string" ||
    !isNullableString(data.handled_by) ||
    !isNullableString(data.handled_at)
  ) {
    return null
  }

  return {
    ...incident,
    action: data.action,
    handled_by: data.handled_by,
    handled_at: data.handled_at,
  }
}

export function asCameraStatusUpdateData(
  data: Record<string, unknown>,
): CameraStatusUpdateData | null {
  if (
    typeof data.camera_id !== "number" ||
    typeof data.camera_name !== "string" ||
    typeof data.is_enabled !== "boolean" ||
    typeof data.desired_ai_state !== "string" ||
    !isNullableString(data.desired_state_reason) ||
    !isCameraConnectionStatus(data.connection_status) ||
    !isCameraAiStatus(data.ai_status) ||
    !isNullableString(data.cooldown_until) ||
    typeof data.config_version !== "number"
  ) {
    return null
  }

  return {
    camera_id: data.camera_id,
    camera_name: data.camera_name,
    is_enabled: data.is_enabled,
    desired_ai_state: data.desired_ai_state,
    desired_state_reason: data.desired_state_reason,
    connection_status: data.connection_status,
    ai_status: data.ai_status,
    cooldown_until: data.cooldown_until,
    config_version: data.config_version,
  }
}

export function asSnoozeActivatedData(data: Record<string, unknown>): SnoozeActivatedData | null {
  if (
    typeof data.log_id !== "number" ||
    typeof data.camera_id !== "number" ||
    !isNullableString(data.snoozed_by) ||
    typeof data.snoozed_until !== "string"
  ) {
    return null
  }

  return {
    log_id: data.log_id,
    camera_id: data.camera_id,
    snoozed_by: data.snoozed_by,
    snoozed_until: data.snoozed_until,
  }
}

export function asReAlarmData(data: Record<string, unknown>): ReAlarmData | null {
  if (typeof data.log_id !== "number" || typeof data.camera_id !== "number") {
    return null
  }

  return {
    log_id: data.log_id,
    camera_id: data.camera_id,
  }
}

export function asMaintenanceNoticeData(
  data: Record<string, unknown>,
): MaintenanceNoticeData | null {
  if (typeof data.message !== "string" || !isNullableString(data.backup_id)) {
    return null
  }

  return {
    message: data.message,
    backup_id: data.backup_id,
  }
}
