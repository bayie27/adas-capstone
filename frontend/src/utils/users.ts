import type { ApiUserRole } from "@/api/auth"
import type { UserRecord } from "@/api/users"
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

  if (username) {
    // No first/last name: derive from the username, splitting on whitespace and
    // underscores so e.g. "john_doe" → "JD".
    return username
      .split(/[\s_]+/)
      .map((word) => word[0]?.toUpperCase() ?? "")
      .slice(0, 2)
      .join("")
  }

  return "US"
}

export function formatUserRole(role: ApiUserRole) {
  return mapApiRoleToAppRole(role) ?? role
}
