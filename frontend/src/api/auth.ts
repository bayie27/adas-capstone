import axios from "axios"
import { API_BASE_URL } from "@/utils/env"

export type ApiUserRole = "Admin" | "Operator"

export interface LoginCredentials {
  username: string
  password: string
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

const authApi = axios.create({ baseURL: API_BASE_URL, withCredentials: true })

export async function logoutUser() {
  await authApi.post("/auth/logout")
}
