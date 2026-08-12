import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useAuthStore } from "@/store/useAuthStore"
import type { AppUserRole } from "@/types/auth"
import { getDefaultRouteForRole } from "@/utils/auth"

interface ProtectedRouteProps {
  children: ReactNode
  requiredRole: AppUserRole
}

export function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  // `role` is a display cache (P2, D-006), not proof of authentication —
  // the actual session lives in an HttpOnly cookie the backend verifies on
  // every request. A stale/invalid cookie still 401s and gets caught by
  // api.ts's response interceptor, which clears this cache and redirects.
  const role = useAuthStore((state) => state.role)

  if (!role) {
    return <Navigate to="/login" replace />
  }

  if (role !== requiredRole) {
    return <Navigate to={getDefaultRouteForRole(role)} replace />
  }

  return <>{children}</>
}
