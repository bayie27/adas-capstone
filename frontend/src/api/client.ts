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

// `AUTH_INVALID_CREDENTIALS` is a 401 too, but it means "the password you
// just re-submitted for this action is wrong" (login, and the restore
// modal's re-auth step) — the session cookie itself is still perfectly
// valid. Only AUTH_REQUIRED / AUTH_EXPIRED / AUTH_REVOKED (dependencies.py)
// mean the session actually needs the operator bounced to /login; treating
// every 401 the same forced a hard reload out of the restore modal on a
// mistyped password instead of showing the inline "incorrect password"
// error the modal already renders for exactly this response.
const SESSION_LOSS_EXCLUDED_CODES = new Set(["AUTH_INVALID_CREDENTIALS"])

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const code = error.response?.data?.code
    if (
      error.response?.status === 401 &&
      authRedirectSuspensions === 0 &&
      !SESSION_LOSS_EXCLUDED_CODES.has(code)
    ) {
      useAuthStore.getState().clearSession()
      redirectToLogin("Your session expired. Please sign in again.")
    }

    return Promise.reject(error)
  },
)

// 01_CONTRACTS.md §1.3 — the error envelope, parsed here rather than
// re-derived at each call site.

/**
 * The stable error-code catalog. The first ten are the per-status defaults
 * (`_DEFAULT_ERROR_CODES` in `app/schemas/common.py`); the rest are the codes
 * routes raise explicitly when the status code's generic default is not
 * specific enough — a duplicate 409 versus a lost-race 409, for instance.
 *
 * `(string & {})` keeps the union open: an unrecognised code from a newer
 * backend still type-checks as a string rather than failing to compile, while
 * the known members still autocomplete and still narrow.
 */
export type ApiErrorCode =
  | "PRECONDITION_FAILED"
  | "AUTH_REQUIRED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "CONFLICT_STATE"
  | "PAYLOAD_TOO_LARGE"
  | "VALIDATION_ERROR"
  | "AUTH_RATE_LIMITED"
  | "INTERNAL_SERVER_ERROR"
  | "TEMPORARILY_UNAVAILABLE"
  | "CONFLICT_DUPLICATE"
  | "AUTH_INVALID_CREDENTIALS"
  | "AUTH_EXPIRED"
  | "AUTH_REVOKED"
  | "ORIGIN_REJECTED"
  | "CONFLICT_BUSY"
  | (string & {})

/** A 422 field-level validation failure, from the body's `errors[]`. */
export interface ApiValidationError {
  field?: string
  message?: string
  [key: string]: unknown
}

/**
 * An `ApiError` response, parsed once. Callers branch on `code` — a 429
 * rate-limit, a 409 lost race and a 503 SQLite-busy are three different
 * situations that were previously indistinguishable from `detail` alone.
 */
export interface ParsedApiError {
  status: number
  code: ApiErrorCode
  detail: string
  /** Populated on 422 only. */
  errors: ApiValidationError[]
  /**
   * Everything the route merged into the body beyond the three envelope keys.
   *
   * `AppHTTPException(..., extra={...})` (`app/core/errors.py`) merges its
   * `extra` dict into the JSON body at the **top level**, alongside `detail`
   * and `code` — it is not nested. The 409 CONFLICT_STATE from a lost HITL
   * race is the case that matters: `_conflict_response` in `routes/alerts.py`
   * attaches `current_status` / `handled_action` / `handled_by` / `handled_at`
   * and its own docstring calls this "the exact 409 body the frontend's
   * already-handled modal depends on".
   *
   * Parsing stopped at the three known keys, so all four were discarded before
   * any call site could reach them — the same class of defect as the response
   * types in C2, and invisible to `tsc` for the same reason.
   */
  extra: Record<string, unknown>
}

const ENVELOPE_KEYS = new Set(["detail", "code", "errors"])

/** Returns `null` when the failure is not an `ApiError` response at all. */
export function getApiError(error: unknown): ParsedApiError | null {
  if (!axios.isAxiosError<ApiErrorEnvelope>(error) || !error.response) {
    return null
  }

  const body = error.response.data
  if (!body || typeof body.code !== "string") {
    return null
  }

  const extra: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(body)) {
    if (!ENVELOPE_KEYS.has(key)) extra[key] = value
  }

  return {
    status: error.response.status,
    code: body.code,
    detail: typeof body.detail === "string" ? body.detail : "",
    errors: Array.isArray(body.errors) ? body.errors : [],
    extra,
  }
}

type ApiErrorEnvelope = {
  detail?: string
  code?: string
  errors?: ApiValidationError[]
  [key: string]: unknown
}

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
