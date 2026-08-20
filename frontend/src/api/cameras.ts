import api from "@/api/client"

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
  /**
   * String-typed to match the backend's own three-value parse exactly
   * (`_parse_is_active_filter`, `routes/cameras.py`) — the identical design
   * already shipped for `GetUsersParams` (P19 §3, `api/users.ts`). Omitted
   * entirely preserves today's default (active-only) behavior byte-for-byte.
   * `"false"` surfaces soft-deleted cameras so they can be found and
   * restored; `"null"` lists both.
   */
  is_active?: "true" | "false" | "null"
  search?: string
  limit?: number
  offset?: number
}

/**
 * `GET /api/cameras/{camera_id}` (P21 Step 1, `schemas/camera.py:32-44`) —
 * `CameraRecord` plus the seven AI-owned telemetry columns the list route
 * never exposed. `connection_status`/`ai_status` are staleness-presented
 * exactly as the list presents them, so the drawer and the row can never
 * disagree. Every field is nullable by design: a camera the engine has
 * never reported on has `measured_fps: null` ("no measurement yet"), never
 * a fabricated zero.
 */
export interface CameraDetail extends CameraRecord {
  applied_config_version: number | null
  last_heartbeat_at: string | null
  measured_fps: number | null
  inference_latency_ms: number | null
  last_error_code: string | null
  last_error_message: string | null
  /**
   * Admin-only within an otherwise operator-visible route — `null` for an
   * Operator, not an error. Arrives pre-masked by the backend
   * (`rtsp://***:***@host:port/path`); there is no real value to "reveal"
   * behind it, and nothing here attempts to reconstruct one.
   */
  rtsp_url_redacted: string | null
}

export async function getCameraDetail(cameraId: number) {
  const { data } = await api.get<CameraDetail>(`/cameras/${cameraId}`)
  return data
}

export interface CreateCameraInput {
  camera_name: string
  channel_id: number
}

export interface UpdateCameraInput {
  camera_name?: string
  channel_id?: number
  is_enabled?: boolean
  /**
   * `false` -> `true` restores a soft-deleted camera. `true` -> `false`
   * (i.e. sending `is_active: false`) is rejected by the backend with a
   * plain 400 — DELETE stays the only path for deactivating, since it's the
   * only one that checks for an open incident first. Never send
   * `is_active: false` here; call `deleteCamera` instead.
   */
  is_active?: boolean
}

export async function getCameras(params: GetCamerasParams) {
  const { data } = await api.get<CameraListResponse>("/cameras/", {
    params,
  })

  return data
}

export async function createCamera(input: CreateCameraInput) {
  const { data } = await api.post<CameraRecord>("/cameras/", input)
  return data
}

export async function updateCamera(cameraId: number, input: UpdateCameraInput) {
  const { data } = await api.patch<CameraRecord>(`/cameras/${cameraId}`, input)
  return data
}

export async function deleteCamera(cameraId: number) {
  await api.delete(`/cameras/${cameraId}`)
}

/** The counterpart to `deleteCamera` — a thin wrapper over `updateCamera`
 * so call sites don't construct the `{ is_active: true }` payload inline. */
export async function restoreCamera(cameraId: number) {
  return updateCamera(cameraId, { is_active: true })
}
