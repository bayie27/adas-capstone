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

export default api
