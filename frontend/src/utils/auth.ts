import type { ApiUserRole } from "@/api/auth"

const VALID_API_ROLES: readonly ApiUserRole[] = ["Admin", "Operator"]

/**
 * Narrows an unknown value to the backend's own role enum. The frontend used
 * to invent a parallel `Administrator | Operator` type and map into it, which
 * put a second identity through the auth store, the route guard, the sidebar
 * and the Detections filter. "Administrator" is a string Figma renders — a
 * display concern, not a domain type. See `formatUserRole` in utils/format.
 */
export function toApiRole(role: string | null | undefined): ApiUserRole | null {
  if (!role) {
    return null
  }

  return VALID_API_ROLES.includes(role as ApiUserRole) ? (role as ApiUserRole) : null
}

export function getDefaultRouteForRole(role: ApiUserRole | null) {
  if (role === "Admin") {
    return "/admin"
  }

  if (role === "Operator") {
    return "/user"
  }

  return "/login"
}
