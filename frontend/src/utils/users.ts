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

export function formatShortDateTime(value: string | null) {
  if (!value) {
    return "-"
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return "-"
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date)
}

export function formatRelativeDateTime(value: string | null) {
  if (!value) {
    return "Never"
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return "-"
  }

  const diffMs = date.getTime() - Date.now()
  const diffMinutes = Math.round(diffMs / 60000)

  if (Math.abs(diffMinutes) < 1) {
    return "Just now"
  }

  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" })

  if (Math.abs(diffMinutes) < 60) {
    return formatter.format(diffMinutes, "minute")
  }

  const diffHours = Math.round(diffMinutes / 60)

  if (Math.abs(diffHours) < 24) {
    return formatter.format(diffHours, "hour")
  }

  const diffDays = Math.round(diffHours / 24)

  if (Math.abs(diffDays) < 7) {
    return formatter.format(diffDays, "day")
  }

  return formatShortDateTime(value)
}
