// Presentation formatters and option lists, consolidated from the four
// per-domain utils modules. These format values for display; they are not
// part of any endpoint contract, which is why they stay in utils/ rather than
// moving into api/ with the shapes they read.

import type { AlertLog, AlertStatus } from "@/api/alerts"
import { formatFullDateTime, formatTimeOnly } from "@/utils/datetime"
import type { CameraAiStatus, CameraConnectionStatus, CameraRecord } from "@/api/cameras"
import type { ApiUserRole } from "@/api/auth"
import type { UserRecord } from "@/api/users"

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
    return "bg-warning text-canvas"
  }

  if (status === "Resolved") {
    return "bg-success text-canvas"
  }

  if (status === "Dismissed") {
    return "bg-fg-muted text-canvas"
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

/**
 * Why a camera is not detecting, in words.
 *
 * `ai_status` alone cannot say. The AI engine reports `Paused` for a camera
 * halted by an open incident and for one serving a dismiss cooldown, and a
 * disabled camera reads `Inactive` exactly like a broken one — three
 * different situations that used to render as the same word, only one of
 * which is waiting on an operator.
 *
 * The distinction is backend-owned (`desired_state_reason`, D-003), so this
 * is a lookup, not a derivation. Figma draws no second line here; the
 * treatment is StatusText's `description`, which is the app's existing idiom
 * for qualifying a status.
 *
 * Returns `null` when the camera is in its normal state, or when the backend
 * sends a reason this build doesn't know — an unrecognised value says
 * nothing rather than guessing.
 */
export function describeCameraDesiredState(
  camera: Pick<CameraRecord, "desired_state_reason" | "cooldown_until">,
  now: number,
): string | null {
  switch (camera.desired_state_reason) {
    case "disabled":
      return "Detection turned off for this camera"
    case "incident":
      return "Held for an open incident — resumes when an operator closes it"
    case "cooldown": {
      const remaining = secondsUntil(camera.cooldown_until, now)
      return remaining === null
        ? "Dismissal cooldown"
        : remaining > 0
          ? `Dismissal cooldown — resumes in ${remaining}s`
          : "Dismissal cooldown — resuming"
    }
    default:
      return null
  }
}

/** Whole seconds from `now` until an ISO deadline; `null` if unparsable. */
export function secondsUntil(deadline: string | null, now: number): number | null {
  if (!deadline) return null
  const target = new Date(deadline).getTime()
  if (Number.isNaN(target)) return null
  return Math.max(0, Math.ceil((target - now) / 1000))
}

/**
 * D-2: the muted-row description, same shape as the dismissal-cooldown line
 * above — "who" is optional because it can only ever resolve to a name for
 * an Admin (GET /api/users/ is admin-only) or when the id is within
 * useUserOptions' 100-user cap (Q10); otherwise the caller passes the raw
 * id, which still names *something* rather than nothing.
 */
export function describeSnoozeStatus(
  snoozedUntil: string | null,
  now: number,
  who: string | null,
  snoozedAt?: string | null,
): string | null {
  if (!snoozedUntil) return null
  const remaining = secondsUntil(snoozedUntil, now)
  const suffix = who ? ` by ${who}` : ""
  const startedAt = formatTimeOnly(snoozedAt)
  const prefix = startedAt ? `Muted at ${startedAt}` : `Muted`
  if (remaining === null) return `${prefix}${suffix}`
  if (remaining <= 0) return `${prefix}${suffix} — resuming`
  return `${prefix}${suffix} — resumes in ${remaining}s`
}

/** Is this camera counting down a cooldown that a clock needs to tick for? */
export function isCameraInCooldown(camera: Pick<CameraRecord, "desired_state_reason">) {
  return camera.desired_state_reason === "cooldown"
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

/**
 * The backend enum is `Admin | Operator`; Figma renders the first as
 * "Administrator" in the Users table and the sidebar footer. That is a
 * formatting concern, which is why it is a formatter here rather than a
 * second role type threaded through the store and the route guard.
 */
export function formatUserRole(role: ApiUserRole | null | undefined) {
  if (role === "Admin") return "Administrator"
  if (role === "Operator") return "Operator"
  return "Unknown Role"
}

/** A backup's `file_size` in bytes, adaptive to the smallest unit that reads
 * as a whole-ish number rather than a wall of decimal places. */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  if (mb < 1024) return `${mb.toFixed(1)} MB`
  return `${(mb / 1024).toFixed(2)} GB`
}
