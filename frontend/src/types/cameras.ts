export type CameraConnectionStatus = "Connected" | "Disconnected" | "Reconnecting" | "Unresponsive"

export type CameraAiStatus = "Active" | "Inactive" | "Paused" | "Unresponsive"

export interface CameraRecord {
  camera_id: number
  camera_name: string
  channel_id: number
  connection_status: CameraConnectionStatus
  ai_status: CameraAiStatus
  is_enabled: boolean
  is_active: boolean
  // Backend-owned desired state (D-003). `config_version` is the merge key for
  // CAMERA_STATUS_UPDATE per 01_CONTRACTS.md §9.5 — an event carrying an older
  // version than the cached record must not be applied.
  desired_ai_state: string
  desired_state_reason: string | null
  cooldown_until: string | null
  config_version: number
  created_at: string
  updated_at: string
}

export interface CameraKpis {
  total: number
  enabled: number
  network_connected: number
  active_detection: number
}

export interface CameraConnectionBreakdown {
  connected: number
  disconnected: number
  reconnecting: number
  unresponsive: number
}

export interface CameraAiBreakdown {
  active: number
  paused: number
  inactive: number
  unresponsive: number
}

export interface CameraBreakdowns {
  connection: CameraConnectionBreakdown
  ai: CameraAiBreakdown
}

// 01_CONTRACTS.md §5.9 — kpis/breakdowns describe the whole active population;
// `cameras` is the filtered, paginated page.
export interface CameraListResponse {
  kpis: CameraKpis
  breakdowns: CameraBreakdowns
  total_filtered: number
  cameras: CameraRecord[]
}

export interface GetCamerasParams {
  connection_status?: CameraConnectionStatus[]
  ai_status?: CameraAiStatus[]
  is_enabled?: boolean
  search?: string
  limit?: number
  offset?: number
}

export interface CreateCameraInput {
  camera_name: string
  channel_id: number
}

export interface UpdateCameraInput {
  camera_name?: string
  channel_id?: number
  is_enabled?: boolean
}
