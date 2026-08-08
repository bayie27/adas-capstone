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
  created_at: string
  updated_at: string
}

export interface CameraListResponse {
  total_cameras: number
  network_connected: number
  active_detection: number
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
