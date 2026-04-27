import axios, { type InternalAxiosRequestConfig } from "axios"

import { API_BASE_URL } from "@/config/env"
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

function redirectToLogin() {
  if (window.location.pathname !== LOGIN_PATH) {
    window.location.replace(LOGIN_PATH)
  }
}

api.interceptors.request.use(attachAuthorizationHeader)

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // A single 401 policy keeps token expiry/logout behavior consistent across the app.
      useAuthStore.getState().clearSession()
      redirectToLogin()
    }

    return Promise.reject(error)
  },
)

export default api
