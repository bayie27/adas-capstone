import api from "@/api/client"
import { API_BASE_URL } from "@/utils/env"

export interface GpuRead {
  index: number
  name: string
  usage_percent: number | null
  temp_c: number | null
  mem_used_mb: number | null
  mem_total_mb: number | null
  mem_pct: number | null
}

export interface HealthWarning {
  code: string
  severity: string
  measurement: number | null
  threshold: number | null
}

/**
 * Mirrors `SysHealthLive` in backend/app/schemas/health.py (01_CONTRACTS.md
 * §5.8). This had drifted badly — it declared `gpu_usage`,
 * `gpu_temperature`, `uptime_seconds`, `disk_usage_percent`,
 * `disk_used_gb` and `disk_total_gb`, none of which the backend has ever
 * sent. Because the type asserted they existed, `tsc` happily accepted
 * `live.disk_used_gb.toFixed(1)` and the page threw at runtime on every
 * load.
 *
 * Nullability is copied from the backend deliberately: a per-sensor
 * `_available: false` means that sensor failed on an otherwise-good
 * sample, and `collected_at: null` means the collector has not finished
 * its first sample yet. Both are normal states, not errors, so every
 * measurement is optional and callers must degrade rather than assume.
 */
export interface SystemHealthLiveResponse {
  collected_at: string | null
  stale: boolean

  host_uptime_seconds: number | null
  process_uptime_seconds: number | null

  cpu_usage: number | null
  cpu_usage_available: boolean
  cpu_temp: number | null
  cpu_temp_available: boolean

  ram_usage: number | null
  ram_usage_available: boolean

  disk_total_bytes: number | null
  disk_used_bytes: number | null
  disk_available_bytes: number | null
  disk_percent: number | null
  disk_available: boolean

  gpus: GpuRead[]
  gpu_usage_avg: number | null
  gpu_temp_max: number | null
  gpu_mem_pct_max: number | null

  avg_inference_latency_ms: number | null
  avg_fps: number | null
  sample_camera_count: number

  warnings: HealthWarning[]
  state: "healthy" | "degraded" | "critical"
}

/**
 * Mirrors `HealthHistoryPoint` in backend/app/schemas/health.py. One shape
 * shared by both raw (48h) and hourly (30d) ranges — for a raw point the
 * `_avg`/`_peak` variants of the same metric are identical, so the chart
 * never has to branch on `range`.
 */
export interface SystemHealthDataPoint {
  timestamp: string
  cpu_usage: number | null
  ram_usage: number | null
  gpu_usage: number | null
  cpu_temp_avg: number | null
  cpu_temp_peak: number | null
  gpu_temp_peak: number | null
  gpu_mem_pct_avg: number | null
  gpu_mem_pct_peak: number | null
  sample_count: number
}

export interface SystemHealthHistoryResponse {
  range: "48h" | "30d"
  points: SystemHealthDataPoint[]
}

// `api`'s baseURL is `http://host:8000/api`, but the probes are served at
// the origin root (`GET /healthz/*`), not under `/api`. Strip the `/api`
// suffix so the ping targets the URL the docstrings actually claim.
const BACKEND_ORIGIN = API_BASE_URL.replace(/\/api$/, "")

/**
 * Verifies the backend is actually serving requests, not merely that the
 * process is alive. This was pinging `GET /` and treating any response as
 * healthy — weaker than either real probe. `/healthz/live` returns 200 with
 * no DB touch at all, so it can read "online" from a backend whose database
 * is unreachable; `/healthz/ready` genuinely verifies DB access and 503s
 * otherwise, which is what an operator-facing "backend online" dot should
 * mean. Resolves `true` on a 2xx, `false` on any error (including the 503
 * `/healthz/ready` returns while not ready).
 */
export async function getSystemHealth(): Promise<boolean> {
  try {
    await api.get("/healthz/ready", { baseURL: BACKEND_ORIGIN })
    return true
  } catch {
    return false
  }
}

export async function getSystemHealthLive(): Promise<SystemHealthLiveResponse> {
  const { data } = await api.get<SystemHealthLiveResponse>("/system/health/live")
  return data
}

export async function getSystemHealthHistory(
  range: "48h" | "30d",
): Promise<SystemHealthHistoryResponse> {
  const { data } = await api.get<SystemHealthHistoryResponse>("/system/health/history", {
    params: { range },
  })
  return data
}
