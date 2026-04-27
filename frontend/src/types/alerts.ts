export type AlertStatus = "Unverified" | "Ongoing" | "Dismissed" | "Resolved"

export interface AlertLog {
  log_id: number
  camera_id: number
  detected_at: string
  snapshot_path: string
  confidence_score: number
  detection_status: AlertStatus
  verified_by_id: number | null
  verified_by_name: string | null
  verified_at: string | null
  closed_by_id: number | null
  closed_by_name: string | null
  closed_at: string | null
  camera_name: string | null
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
