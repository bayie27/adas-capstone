export interface SystemHealthLiveResponse {
  cpu_usage: number
  gpu_usage: number
  ram_usage: number
  gpu_temperature: number
  disk_usage_percent: number
  disk_used_gb: number
  disk_total_gb: number
  uptime_seconds: number
  avg_inference_latency_ms: number | null
  avg_fps: number | null
}

export interface SystemHealthDataPoint {
  timestamp: string
  cpu_usage: number
  gpu_usage: number
  ram_usage: number
  gpu_temperature: number
}

export interface SystemHealthHistoryResponse {
  range: "48h" | "30d"
  data: SystemHealthDataPoint[]
}
