import type { ApiUserRole } from "@/types/auth"
import type { UserRecord } from "@/types/users"
import { mapApiRoleToAppRole } from "@/utils/auth"

export function getUserFullName(user: Pick<UserRecord, "first_name" | "last_name">) {
  return [user.first_name, user.last_name].filter(Boolean).join(" ").trim()
}

export function getUserInitials(firstName: string, lastName: string, username?: string | null) {
  const initials = [firstName, lastName]
    .filter(Boolean)
    .map((value) => value[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 2)

  if (initials) {
    return initials
  }

  return username?.slice(0, 2).toUpperCase() ?? "US"
}

export function formatUserRole(role: ApiUserRole) {
  return mapApiRoleToAppRole(role) ?? role
}
