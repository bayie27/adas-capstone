import axios from "axios"
import { API_BASE_URL } from "@/utils/env"
import api from "@/services/api"
import type { CurrentUserResponse, LoginCredentials, LoginResponse } from "@/types/auth"

const authApi = axios.create({
  baseURL: API_BASE_URL,
  // The login/logout requests carry or receive the session cookie too.
  withCredentials: true,
})

export async function loginUser(credentials: LoginCredentials) {
  const formData = new URLSearchParams()
  formData.set("username", credentials.username.trim())
  formData.set("password", credentials.password)

  const { data } = await authApi.post<LoginResponse>("/auth/login", formData, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  })

  return data
}

export async function logoutUser() {
  await authApi.post("/auth/logout")
}

export async function getCurrentUser() {
  const { data } = await api.get<CurrentUserResponse>("/users/me")

  return data
}
