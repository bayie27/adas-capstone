import api from "@/services/api"
import type { SystemHealthHistoryResponse, SystemHealthLiveResponse } from "@/types/health"

/**
 * Pings the backend root URL to verify server connectivity.
 * Resolves `true` when the server responds, `false` on any error.
 */
export async function getSystemHealth(): Promise<boolean> {
  try {
    await api.get("/")
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
