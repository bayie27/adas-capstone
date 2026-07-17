import axios, { type InternalAxiosRequestConfig } from "axios"

import { API_BASE_URL } from "@/utils/env"
import { useAuthStore } from "@/store/useAuthStore"

const LOGIN_PATH = "/login"

const api = axios.create({
  baseURL: API_BASE_URL,
  // FastAPI expects repeated query params like `status=a&status=b`, not indexed arrays.
  paramsSerializer: {
    indexes: null,
  },
  headers: {
    "Content-Type": "application/json",
  },
})

function attachAuthorizationHeader(config: InternalAxiosRequestConfig) {
  const token = useAuthStore.getState().token

  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`)
  }

  return config
}

function redirectToLogin(message?: string) {
  if (typeof window !== "undefined" && message) {
    window.sessionStorage.setItem("auth-message", message)
  }

  if (window.location.pathname !== LOGIN_PATH) {
    window.location.replace(LOGIN_PATH)
  }
}

api.interceptors.request.use(attachAuthorizationHeader)

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
