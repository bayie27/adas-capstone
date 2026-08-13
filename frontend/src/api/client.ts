import axios from "axios"

import { API_BASE_URL } from "@/utils/env"
import { useAuthStore } from "@/store/useAuthStore"

const LOGIN_PATH = "/login"

const api = axios.create({
  baseURL: API_BASE_URL,
  // Send + receive the HttpOnly session cookie (P2, D-006) — there is no
  // token to attach as an Authorization header anymore.
  withCredentials: true,
  // FastAPI expects repeated query params like `status=a&status=b`, not indexed arrays.
  paramsSerializer: {
    indexes: null,
  },
  headers: {
    "Content-Type": "application/json",
  },
})

export function redirectToLogin(message?: string) {
  if (typeof window !== "undefined" && message) {
    window.sessionStorage.setItem("auth-message", message)
  }

  if (window.location.pathname !== LOGIN_PATH) {
    window.location.replace(LOGIN_PATH)
  }
}

// A dev-tools reseed deletes every auth_session row and issues a
// replacement cookie in the same response. Requests already in flight when
// that happens come back 401 through no fault of the user, and the handler
// below would clear the session and bounce them to /login — which is
// exactly what DT-2 exists to prevent. Suspending is a counter, not a
// boolean, so overlapping callers can't release each other's guard.
let authRedirectSuspensions = 0

export function suspendAuthRedirect(): () => void {
  authRedirectSuspensions += 1
  let released = false
  return () => {
    if (released) return
    released = true
    authRedirectSuspensions -= 1
  }
}

// Exposed so other session-loss signals besides this axios interceptor —
// notably the WebSocket's SESSION_LOST close codes in RealtimeAlertsBridge —
// can honor the same guard instead of bouncing the operator mid-reseed.
export function isAuthRedirectSuspended(): boolean {
  return authRedirectSuspensions > 0
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && authRedirectSuspensions === 0) {
      useAuthStore.getState().clearSession()
      redirectToLogin("Your session expired. Please sign in again.")
    }

    return Promise.reject(error)
  },
)

// 01_CONTRACTS.md §1.3 — the error envelope, parsed here rather than
// re-derived at each call site.
type ValidationIssue = {
  msg?: string
}

type ApiErrorBody = {
  detail?: string | ValidationIssue[]
}

export function getApiErrorMessage(error: unknown, fallback: string) {
  if (!axios.isAxiosError<ApiErrorBody>(error)) {
    return fallback
  }

  const detail = error.response?.data?.detail

  if (typeof detail === "string" && detail.trim()) {
    return detail
  }

  if (Array.isArray(detail)) {
    const validationMessage = detail
      .map((issue) => issue.msg?.trim())
      .filter((message): message is string => Boolean(message))
      .join(" ")

    if (validationMessage) {
      return validationMessage
    }
  }

  return fallback
}

export default api
