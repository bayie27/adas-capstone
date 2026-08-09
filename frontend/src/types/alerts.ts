export type AlertStatus = "Unverified" | "Ongoing" | "Dismissed" | "Resolved"

export interface AlertLog {
  log_id: number
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
  snoozed_until: string | null
  snoozed_by_id: number | null
}

export interface AlertListResponse {
  total_filtered: number
  logs: AlertLog[]
}

export interface GetAlertsParams {
  start_date?: string
  end_date?: string
  status?: AlertStatus[]
  camera_id?: number[]
  user_id?: number[]
  search?: string
  limit?: number
  offset?: number
}
