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

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().clearSession()
      redirectToLogin("Your session expired. Please sign in again.")
    }

    return Promise.reject(error)
  },
)

export default api
