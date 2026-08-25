import api from "@/api/client"
import { downloadBlobResponse } from "@/utils/download"
import type { ExportFormat } from "@/components/ui/ExportButton"

/**
 * The 27-entry action catalog (`AUDIT_ACTIONS`, `app/models/audit.py`),
 * mirrored here rather than fetched — there is no options endpoint for it
 * (only `GET /` and `GET /export` exist on this router), and unlike
 * Phase 14's alarm-sound allowlist this one is a fixed, migration-gated
 * StrEnum backed by a database CHECK constraint, not runtime config that
 * could silently drift. The plan's own PR body says as much: "the client
 * mirrors that catalog rather than accepting free text." An unlisted value
 * is still a 422 server-side regardless of what this list contains.
 */
export const AUDIT_ACTIONS = [
  "LOGIN_SUCCESS",
  "LOGIN_FAILURE",
  "LOGOUT",
  "ALERT_CONFIRM",
  "ALERT_DISMISS",
  "ALERT_RESOLVE",
  "ALERT_CORRECTION",
  "ALERT_SNOOZE",
  "CAMERA_CREATE",
  "CAMERA_UPDATE",
  "CAMERA_ENABLE",
  "CAMERA_DISABLE",
  "CAMERA_DELETE",
  "CAMERA_RESTORE",
  "REPORT_EXPORT",
  "AUDIT_EXPORT",
  "USER_CREATE",
  "USER_UPDATE",
  "USER_ENABLE",
  "USER_DISABLE",
  "USER_ROLE_CHANGE",
  "USER_PASSWORD_RESET",
  "USER_PROFILE_UPDATE",
  "USER_PASSWORD_CHANGE",
  "ALARM_SETTINGS_UPDATE",
  "BACKUP_TRIGGER",
  "RESTORE_TRIGGER",
] as const

export type AuditAction = (typeof AUDIT_ACTIONS)[number]

/** `AuditResult` (`app/models/enums.py`) — a 3-value StrEnum, same reasoning as AUDIT_ACTIONS. */
export const AUDIT_RESULTS = ["success", "denied", "failure"] as const
export type AuditResult = (typeof AUDIT_RESULTS)[number]

/**
 * `target_type` has no enum on the backend — it's a free `str` column, one
 * literal string per call site (`audit.record(..., target_type="camera")`
 * and friends). Enumerated here by grepping every such call site rather
 * than guessed: `backup`, `camera`, `export`, `incident`, `restore`,
 * `session`, `user`. Same reasoning as AUDIT_ACTIONS — these are literal
 * strings in the backend's own source, not data that could add a new value
 * without a code change, so mirroring them is a real reflection of the
 * backend, not a stand-in for one.
 */
export const AUDIT_TARGET_TYPES = [
  "backup",
  "camera",
  "export",
  "incident",
  "restore",
  "session",
  "user",
] as const

/**
 * The six fields `AUDIT_SORT_FIELDS` (`routes/audit.py:28`) allows.
 * `audit_id` is always applied as a tie-break server-side even when sorting
 * by something else, so equal-`created_at` rows never shuffle between pages.
 * An unlisted value is a 422, same rule as Phase 7's `ALERT_SORT_FIELDS`.
 */
export const AUDIT_SORT_FIELDS = [
  "audit_id",
  "created_at",
  "action",
  "result",
  "user_id",
  "target_type",
] as const

export type AuditSortField = (typeof AUDIT_SORT_FIELDS)[number]
export type SortOrder = "asc" | "desc"

export interface AuditLogEntry {
  audit_id: number
  actor_type: string
  user_id: number | null
  username: string | null
  role: string | null
  action: string
  target_type: string | null
  target_ref: string | null
  result: string
  detail: Record<string, unknown> | null
  request_id: string | null
  source_ip: string | null
  created_at: string
}

export interface AuditLogListResponse {
  total_filtered: number
  items: AuditLogEntry[]
}

export interface GetAuditLogsParams {
  action?: AuditAction[]
  user_id?: number[]
  result?: AuditResult[]
  target_type?: string
  /**
   * Declared, intentionally unsent: `target_ref` is read and displayed
   * already (`AuditLog.tsx:409`), but nothing on the filter side sets it —
   * the existing `search` box already matches against the backend's
   * `target_ref`, so a dedicated filter field would just duplicate it.
   */
  target_ref?: string
  start_date?: string
  end_date?: string
  search?: string
  sort_by?: AuditSortField
  sort_order?: SortOrder
  limit?: number
  offset?: number
}

export async function getAuditLogs(params: GetAuditLogsParams) {
  const { data } = await api.get<AuditLogListResponse>("/audit-logs/", { params })
  return data
}

/**
 * `GET /api/audit-logs/export` takes the same filter set as the list route
 * plus `sort_by`/`sort_order`/`format`, and — confirmed directly against
 * `routes/audit.py:214` — genuinely accepts `format=csv|pdf` on this
 * synchronous route today, real PDF included, no async job required. This
 * export is itself audited (AUDIT_EXPORT), using a watermark so that row
 * can never appear inside the file it produces; viewing the log is not.
 */
export async function exportAuditLogs(params: GetAuditLogsParams, format: ExportFormat = "csv") {
  const response = await api.get<Blob>("/audit-logs/export", {
    params: { ...params, format },
    responseType: "blob",
  })

  downloadBlobResponse(response, `adas_audit_export.${format}`)
}
