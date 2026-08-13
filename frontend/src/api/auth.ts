import axios from "axios"
import { API_BASE_URL } from "@/utils/env"
import api from "@/api/client"

export type ApiUserRole = "Admin" | "Operator"

export interface LoginCredentials {
  username: string
  password: string
}

export interface LoginResponse {
  user: CurrentUserResponse
}

export interface CurrentUserResponse {
  user_id: number
  username: string
  first_name: string
  last_name: string
  role: ApiUserRole
  is_active: boolean
  created_at: string
  updated_at: string
  password_changed_at: string | null
  last_login: string | null
}

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
