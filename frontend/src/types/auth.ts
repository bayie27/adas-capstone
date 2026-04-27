export type ApiUserRole = "Admin" | "Operator"
export type AppUserRole = "Administrator" | "Operator"

export interface LoginCredentials {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
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
