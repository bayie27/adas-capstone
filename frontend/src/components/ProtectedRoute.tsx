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
  const token = useAuthStore((state) => state.token)
  const role = useAuthStore((state) => state.role)

  if (!token || !role) {
    return <Navigate to="/login" replace />
  }

  if (role !== requiredRole) {
    return <Navigate to={getDefaultRouteForRole(role)} replace />
  }

  return <>{children}</>
}
