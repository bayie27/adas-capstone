import axios from "axios"
import { API_BASE_URL } from "@/config/env"
import api from "@/services/api"
import type { CurrentUserResponse, LoginCredentials, LoginResponse } from "@/types/auth"

const authApi = axios.create({
  baseURL: API_BASE_URL,
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

export async function getCurrentUser(accessToken: string) {
  const { data } = await api.get<CurrentUserResponse>("/users/me", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })

  return data
}
