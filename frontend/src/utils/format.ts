// Presentation formatters and option lists, consolidated from the four
// per-domain utils modules. These format values for display; they are not
// part of any endpoint contract, which is why they stay in utils/ rather than
// moving into api/ with the shapes they read.

import type { AlertLog, AlertStatus } from "@/api/alerts"
import { formatFullDateTime } from "@/utils/datetime"
import type { CameraAiStatus, CameraConnectionStatus, CameraRecord } from "@/api/cameras"
import type { ApiUserRole } from "@/api/auth"
import type { UserRecord } from "@/api/users"
import { mapApiRoleToAppRole } from "@/utils/auth"

// ---- alerts ----
export function formatAlertCode(logId: number) {
  return `ACC-${logId.toString().padStart(6, "0")}`
}

export function formatAlertConfidence(score: number) {
  return `${(score * 100).toFixed(1)}%`
}

export function getAlertLastHandledBy(alert: AlertLog) {
  if (alert.closed_by_name) {
    return alert.closed_by_name
  }

  if (alert.verified_by_name) {
    return alert.verified_by_name
  }

  return "-"
}

export function getAlertLastUpdated(alert: AlertLog) {
  if (alert.closed_at) {
    return formatFullDateTime(alert.closed_at)
  }

  if (alert.verified_at) {
    return formatFullDateTime(alert.verified_at)
  }

  return "-"
}

export function getAlertStatusTextClass(status: AlertStatus) {
  if (status === "Ongoing") {
    return "text-warning"
  }

  if (status === "Resolved") {
    return "text-success"
  }

  if (status === "Unverified") {
    return "text-fg"
  }

  return "text-fg-muted"
}

export function getAlertBadgeClass(status: AlertStatus) {
  if (status === "Ongoing") {
    return "bg-warning text-fg-on-primary"
  }

  if (status === "Resolved") {
    return "bg-success text-fg-on-primary"
  }

  if (status === "Unverified") {
    return "bg-primary text-fg-on-primary"
  }

  return "bg-surface-3 text-fg"
}

export function getAlertBorderClass(status: AlertStatus) {
  if (status === "Ongoing") {
    return "border-t-amber-500"
  }

  if (status === "Resolved") {
    return "border-t-emerald-500"
  }

  if (status === "Unverified") {
    return "border-t-white"
  }

  return "border-t-fg-muted"
}

// ---- cameras ----
export const CAMERA_CONNECTION_STATUS_OPTIONS: Array<{
  label: string
  value: CameraConnectionStatus | "all"
}> = [
  { label: "All Connections", value: "all" },
  { label: "Connected", value: "Connected" },
  { label: "Disconnected", value: "Disconnected" },
  { label: "Reconnecting", value: "Reconnecting" },
  { label: "Unresponsive", value: "Unresponsive" },
]

export const CAMERA_AI_STATUS_OPTIONS: Array<{
  label: string
  value: CameraAiStatus | "all"
}> = [
  { label: "All AI States", value: "all" },
  { label: "Active", value: "Active" },
  { label: "Inactive", value: "Inactive" },
  { label: "Paused", value: "Paused" },
  { label: "Unresponsive", value: "Unresponsive" },
]

export function getCameraConnectionClass(status: CameraConnectionStatus) {
  if (status === "Connected") {
    return "text-success"
  }

  if (status === "Reconnecting") {
    return "text-warning"
  }

  return "text-danger"
}

export function getCameraAiClass(status: CameraAiStatus) {
  if (status === "Active") {
    return "text-success"
  }

  if (status === "Paused") {
    return "text-warning"
  }

  return "text-danger"
}

export function buildCameraUpdatePayload(
  current: CameraRecord,
  next: { camera_name: string; channel_id: number; is_enabled?: boolean },
) {
  const payload: {
    camera_name?: string
    channel_id?: number
    is_enabled?: boolean
  } = {}

  if (next.camera_name !== current.camera_name) {
    payload.camera_name = next.camera_name
  }

  if (next.channel_id !== current.channel_id) {
    payload.channel_id = next.channel_id
  }

  if (typeof next.is_enabled === "boolean" && next.is_enabled !== current.is_enabled) {
    payload.is_enabled = next.is_enabled
  }

  return payload
}

// ---- analytics ----
export function formatPercent(value: number | null | undefined, fractionDigits = 1) {
  if (value === null || value === undefined) {
    return "N/A"
  }

  return `${(value * 100).toFixed(fractionDigits)}%`
}

export function formatHourLabel(hour: number) {
  return hour.toString().padStart(2, "0")
}

export function truncateLabel(label: string, maxLength = 18) {
  if (label.length <= maxLength) {
    return label
  }

  return `${label.slice(0, maxLength - 3)}...`
}

// ---- users ----
export function getUserFullName(user: Pick<UserRecord, "first_name" | "last_name">) {
  return [user.first_name, user.last_name].filter(Boolean).join(" ").trim()
}

export function getUserInitials(firstName: string, lastName: string, username?: string | null) {
  const initials = [firstName, lastName]
    .filter(Boolean)
    .map((value) => value[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 2)

  if (initials) {
    return initials
  }

  if (username) {
    // No first/last name: derive from the username, splitting on whitespace and
    // underscores so e.g. "john_doe" → "JD".
    return username
      .split(/[\s_]+/)
      .map((word) => word[0]?.toUpperCase() ?? "")
      .slice(0, 2)
      .join("")
  }

  return "US"
}

export function formatUserRole(role: ApiUserRole) {
  return mapApiRoleToAppRole(role) ?? role
}
