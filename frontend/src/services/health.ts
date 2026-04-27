import api from "@/services/api"

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
