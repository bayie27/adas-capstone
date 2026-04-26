import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useAuthStore } from "@/store/useAuthStore"

interface ProtectedRouteProps {
  children: ReactNode
  requiredRole: "Administrator" | "Operator"
}

export function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const token = useAuthStore((state) => state.token)
  const role = useAuthStore((state) => state.role)

  if (!token || !role) {
    return <Navigate to="/login" replace />
  }

  if (requiredRole === "Administrator" && role !== "Administrator") {
    return <Navigate to="/user" replace />
  }

  if (requiredRole === "Operator" && role !== "Operator") {
    return <Navigate to="/admin" replace />
  }

  return <>{children}</>
}
