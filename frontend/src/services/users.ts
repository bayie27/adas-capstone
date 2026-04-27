import api from "@/services/api"
import type {
  ChangeMyPasswordInput,
  CreateUserInput,
  GetUsersParams,
  ResetUserPasswordInput,
  UpdateMyProfileInput,
  UpdateUserInput,
  UserListResponse,
  UserRecord,
} from "@/types/users"

export async function getMyProfile() {
  const { data } = await api.get<UserRecord>("/users/me")
  return data
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
