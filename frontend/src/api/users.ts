import api from "@/api/client"

import type { ApiUserRole } from "@/api/auth"

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
  /**
   * String-typed to match the backend's own three-value parse exactly
   * (`_parse_is_active_filter`, `routes/users.py`) — omitted entirely
   * preserves today's default (active-only) behavior byte-for-byte.
   * `"false"` surfaces deactivated accounts so they can be found and
   * reactivated; `"null"` lists both.
   */
  is_active?: "true" | "false" | "null"
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

export async function getMyProfile() {
  const { data } = await api.get<UserRecord>("/users/me")
  return data
}

/**
 * Scoped by userId so a logged-out session's cached profile can never be
 * served back to the next user who logs in under the same shared
 * QueryClient (see Sidebar.tsx, ProfileSettings.tsx, profile/EditProfileModal.tsx).
 */
export function myProfileQueryKey(userId: number | null) {
  return ["my-profile", userId] as const
}

export async function updateMyProfile(input: UpdateMyProfileInput) {
  const { data } = await api.patch<UserRecord>("/users/me", input)
  return data
}

export async function changeMyPassword(input: ChangeMyPasswordInput) {
  await api.patch("/users/me/password", input)
}

export async function getUsers(params: GetUsersParams) {
  const { data } = await api.get<UserListResponse>("/users/", {
    params,
  })
  return data
}

export async function createUser(input: CreateUserInput) {
  const { data } = await api.post<UserRecord>("/users/", input)
  return data
}

export async function updateUser(userId: number, input: UpdateUserInput) {
  const { data } = await api.patch<UserRecord>(`/users/${userId}`, input)
  return data
}

export async function resetUserPassword(userId: number, input: ResetUserPasswordInput) {
  await api.post(`/users/${userId}/reset-password`, input)
}

export async function deleteUser(userId: number) {
  await api.delete(`/users/${userId}`)
}

/**
 * The counterpart to `deleteUser` — a thin wrapper over `updateUser`
 * that reactivates a deactivated account.
 */
export async function restoreUser(userId: number) {
  return updateUser(userId, { is_active: true })
}
