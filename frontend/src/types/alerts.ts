export type AlertStatus = "Unverified" | "Ongoing" | "Dismissed" | "Resolved"

export interface AlertLog {
  log_id: number
  camera_id: number
  detected_at: string
  // Wire field is `snapshot_key` (01_CONTRACTS.md §7.1), not the pre-P1
  // `snapshot_path` this used to be named. Nullable because a WS-delivered
  // incident doesn't carry it (only `snapshot_url`, which isn't a real route
  // until P4) — it stays null until RealtimeAlertsBridge enriches it via REST.
  snapshot_key: string | null
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
