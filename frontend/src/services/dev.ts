import api from "@/services/api"
import type { ApiUserRole } from "@/types/auth"

/**
 * Thin wrappers over the /api/dev/* routes (dev_plan/02_PKG_dev_api.md §5).
 *
 * These only exist when the backend resolved DEV_TOOLS_ENABLED true — the
 * router is not registered otherwise, so every call here 404s. Probe with
 * useDevTools() before rendering anything that uses them.
 *
 * One caution: the 401 interceptor in services/api.ts calls clearSession()
 * and redirects to /login. `reseed` destroys the session it authenticated
 * with and returns a fresh cookie in the same response, so anything firing
 * a request in the window between the wipe and that cookie landing gets
 * bounced to the login screen. Await the reseed fully before doing
 * anything else.
 */

export interface DevProfileInfo {
  name: string
  description: string
}

export interface DevStatus {
  enabled: boolean
  profiles: DevProfileInfo[]
}

export interface DevSessionUser {
  user_id: number
  username: string
  role: ApiUserRole
}

export interface DevSeedResult {
  profile: string
  users: number
  cameras: number
  detections: number
  audit_rows: number
  health_samples: number
  export_jobs: number
  snapshots: number
  session: DevSessionUser
}

export interface DevCameraStatePayload {
  connection_status?: string
  ai_status?: string
  stale_heartbeat?: boolean
  clear_cooldown?: boolean
}

export async function getDevStatus(): Promise<DevStatus> {
  const { data } = await api.get<DevStatus>("/api/dev/status")
  return data
}

export async function reseedProfile(profile: string, loginAs?: string): Promise<DevSeedResult> {
  const { data } = await api.post<DevSeedResult>("/api/dev/reseed", {
    profile,
    ...(loginAs ? { login_as: loginAs } : {}),
  })
  return data
}

export async function loginAs(username: string): Promise<{ session: DevSessionUser }> {
  const { data } = await api.post<{ session: DevSessionUser }>("/api/dev/login-as", {
    username,
  })
  return data
}

export async function injectDetection(payload: {
  camera_id?: number
  confidence?: number
}): Promise<{ log_id: number; camera_id: number }> {
  const { data } = await api.post("/api/dev/detections", payload)
  return data
}

export async function setCameraState(
  cameraId: number,
  payload: DevCameraStatePayload,
): Promise<void> {
  await api.post(`/api/dev/cameras/${cameraId}/state`, payload)
}

export async function generateHealthHistory(days: number): Promise<number> {
  const { data } = await api.post<{ rows_written: number }>("/api/dev/health-history", {
    days,
  })
  return data.rows_written
}
