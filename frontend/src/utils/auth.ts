import type { ApiUserRole, AppUserRole } from "@/api/auth"

const ROLE_MAP: Record<ApiUserRole, AppUserRole> = {
  Admin: "Administrator",
  Operator: "Operator",
}

export function mapApiRoleToAppRole(role: string | null | undefined): AppUserRole | null {
  if (!role) {
    return null
  }

  return ROLE_MAP[role as ApiUserRole] ?? null
}

export function getDefaultRouteForRole(role: AppUserRole | null) {
  if (role === "Administrator") {
    return "/admin"
  }

  if (role === "Operator") {
    return "/user"
  }

  return "/login"
}
