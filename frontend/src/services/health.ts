import api from "@/services/api"
import type { SystemHealthHistoryResponse, SystemHealthLiveResponse } from "@/types/health"
import { API_BASE_URL } from "@/utils/env"

// `api`'s baseURL is `http://host:8000/api`, but the backend's health route is
// served at the origin root (`GET /`), not under `/api`. Strip the `/api`
// suffix so the ping targets the URL the docstring actually claims.
const BACKEND_ORIGIN = API_BASE_URL.replace(/\/api$/, "")

/**
 * Pings the backend root URL to verify server connectivity.
 * Resolves `true` when the server responds, `false` on any error.
 */
export async function getSystemHealth(): Promise<boolean> {
  try {
    await api.get("/", { baseURL: BACKEND_ORIGIN })
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
