import api, { getApiError } from "@/api/client"
import { downloadBlobResponse } from "@/utils/download"

export type AlertStatus = "Unverified" | "Ongoing" | "Dismissed" | "Resolved"

const ALERT_STATUSES: AlertStatus[] = ["Unverified", "Ongoing", "Dismissed", "Resolved"]

function asAlertStatus(value: unknown): AlertStatus | null {
  return typeof value === "string" && (ALERT_STATUSES as string[]).includes(value)
    ? (value as AlertStatus)
    : null
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null
}

/**
 * Who resolved a race for this incident, and how.
 *
 * The same four facts reach the client by **two different paths**, which is
 * why this is one shape rather than two:
 *
 * - The **409 CONFLICT_STATE** body, when this operator lost the race. Only
 *   the loser gets it — it is a response to their own failed request.
 * - The **`ALERT_STATUS_UPDATE` broadcast**, which reaches *every* connected
 *   dashboard including ones that never made a request. A colleague watching
 *   the same incident should see who handled it without having clicked
 *   anything.
 */
export interface IncidentHandledInfo {
  currentStatus: AlertStatus | null
  handledAction: string | null
  handledBy: string | null
  handledAt: string | null
}

/**
 * Reads the four `extra` fields off a 409 CONFLICT_STATE, or `null` for any
 * other failure. `_conflict_response` (`routes/alerts.py:92`) attaches them
 * specifically so this dialog can name the colleague who got there first; the
 * client used to render the fallback sentence and drop all four.
 */
export function getIncidentConflict(error: unknown): IncidentHandledInfo | null {
  const parsed = getApiError(error)
  if (!parsed || parsed.code !== "CONFLICT_STATE") return null

  return {
    currentStatus: asAlertStatus(parsed.extra.current_status),
    handledAction: asNullableString(parsed.extra.handled_action),
    handledBy: asNullableString(parsed.extra.handled_by),
    handledAt: asNullableString(parsed.extra.handled_at),
  }
}

export interface AlertLog {
  log_id: number
  source_event_id: string
  camera_id: number
  detected_at: string
  // 01_CONTRACTS.md §5.9/§9.3 — an authorized API path (e.g.
  // `/api/alerts/42/snapshot`), never a filesystem key. Always present; the
  // public `/snapshots` static mount is gone as of backend P4.
  snapshot_url: string
  confidence_score: number
  detection_status: AlertStatus
  verified_by_id: number | null
  verified_by_name: string | null
  verified_at: string | null
  closed_by_id: number | null
  closed_by_name: string | null
  closed_at: string | null
  camera_name: string | null
  // "When it was muted" versus snoozed_until's "when it un-mutes" — the
  // audit-shaped fact versus the countdown. DetectionLogRead has always
  // returned this; it was parsed off the wire and discarded because this
  // interface never declared it, the only such drop in the API surface.
  snoozed_at: string | null
  snoozed_until: string | null
  snoozed_by_id: number | null
  created_at: string
  // 01_CONTRACTS.md §9.5 — the merge key for incident events. An
  // ALERT_STATUS_UPDATE older than the incident already held must be dropped.
  updated_at: string
}

export interface AlertListResponse {
  total_filtered: number
  logs: AlertLog[]
}

/**
 * The nine fields `ALERT_SORT_FIELDS` (`routes/alerts.py:51`) allows. An
 * unlisted value is a **422**, so a sort key must always be taken from this
 * list rather than assembled from a column id.
 *
 * Six of the nine have a column on the Detections table (see `SORTABLE` in
 * `Detections.tsx`). The remaining three -- `verified_at`, `closed_at`,
 * `created_at` -- are assessed, not an oversight: none has a column to
 * attach to, there's no operator ask for one, and narrowing this type to
 * six would just be a second source of truth against the backend's own
 * allowlist for no reachability gain.
 */
export const ALERT_SORT_FIELDS = [
  "log_id",
  "detected_at",
  "confidence_score",
  "detection_status",
  "camera_id",
  "verified_at",
  "closed_at",
  "created_at",
  "updated_at",
] as const

export type AlertSortField = (typeof ALERT_SORT_FIELDS)[number]
export type SortOrder = "asc" | "desc"

/** The export routes' `?format=` parameter (`pattern="^(csv|pdf)$"`). */
export type ExportFormat = "csv" | "pdf"

export interface GetAlertsParams {
  start_date?: string
  end_date?: string
  status?: AlertStatus[]
  camera_id?: number[]
  user_id?: number[]
  search?: string
  // `GET /api/alerts/` has always accepted both; this interface declared
  // neither, so the table could not ask for a sort — the parameter was
  // unreachable because the type had no word for it. Defaults server-side to
  // `detected_at desc`, with `log_id` applied as a deterministic tie-break so
  // equal-`detected_at` rows never shuffle between pages.
  sort_by?: AlertSortField
  sort_order?: SortOrder
  limit?: number
  offset?: number
}

export async function getAlerts(params: GetAlertsParams) {
  const { data } = await api.get<AlertListResponse>("/alerts/", {
    params,
  })

  return data
}

/**
 * `GET /api/alerts/export` takes the same filter set as the list route plus
 * `sort_by`, `sort_order` and `format`.
 *
 * This was `exportAlertsCsv(params)` — a name and a signature that both
 * forbade PDF, on a route that has always accepted `?format=csv|pdf`. Passing
 * the sort through matters as much: without it a CSV of a confidence-sorted
 * view arrives in `detected_at` order and quietly is not the thing on screen.
 *
 * Throws on 413 `PAYLOAD_TOO_LARGE` when the filtered row count exceeds
 * `EXPORT_PDF_MAX_ROWS` (10,000) or `EXPORT_CSV_MAX_ROWS` (50,000). The
 * backend's `detail` names the count, the limit and the async jobs endpoint,
 * so callers should render it rather than substituting their own sentence.
 */
export async function exportAlerts(params: GetAlertsParams, format: ExportFormat = "csv") {
  const response = await api.get<Blob>("/alerts/export", {
    params: { ...params, format },
    responseType: "blob",
  })

  downloadBlobResponse(response, `adas_incident_export.${format}`)
}

export async function getAlertDetails(logId: number) {
  const { data } = await api.get<AlertLog>(`/alerts/${logId}`)
  return data
}

export async function confirmAlert(logId: number) {
  const { data } = await api.post<AlertLog>(`/alerts/${logId}/confirm`)
  return data
}

export async function dismissAlert(logId: number) {
  const { data } = await api.post<AlertLog>(`/alerts/${logId}/dismiss`)
  return data
}

export async function resolveAlert(logId: number) {
  const { data } = await api.post<AlertLog>(`/alerts/${logId}/resolve`)
  return data
}

/**
 * Mutes an Unverified incident for the actor's saved duration. **Takes no
 * body** — a client-supplied duration is a 422 (D-004: the duration is the
 * actor's saved `AlarmSettings`, never a request parameter), so this
 * function has no parameter for one either.
 *
 * 400 `PRECONDITION_FAILED` when the incident is no longer Unverified —
 * decidable from a plain read, since a terminal or Ongoing incident can't
 * become Unverified again. 409 `CONFLICT_STATE` on a genuine race, reusing
 * the same already-handled dialog as confirm/dismiss/resolve — callers
 * should check `getIncidentConflict` first and fall back to the plain
 * message only when it returns null, so the two failures render distinctly.
 */
export async function snoozeAlert(logId: number) {
  const { data } = await api.post<AlertLog>(`/alerts/${logId}/snooze`)
  return data
}
