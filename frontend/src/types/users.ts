import type { ApiUserRole } from "@/types/auth"

export interface UserRecord {
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

export interface UserListResponse {
  total_filtered: number
  users: UserRecord[]
}

export interface GetUsersParams {
  search?: string
  limit?: number
  offset?: number
}

export interface UpdateMyProfileInput {
  username?: string
  first_name?: string
  last_name?: string
}

export interface ChangeMyPasswordInput {
  old_password: string
  new_password: string
}

export interface CreateUserInput {
  username: string
  first_name: string
  last_name: string
  role: ApiUserRole
  password: string
}

export interface UpdateUserInput {
  username?: string
  first_name?: string
  last_name?: string
  role?: ApiUserRole
  is_active?: boolean
}

export interface ResetUserPasswordInput {
  new_password: string
}
