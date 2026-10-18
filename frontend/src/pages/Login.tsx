import { useState } from "react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"

import type { CurrentUserResponse } from "@/api/auth"
import { MfaLoginFlow } from "@/pages/auth/MfaLoginFlow"
import { useAuthStore } from "@/store/useAuthStore"
import { getDefaultRouteForRole } from "@/utils/auth"

function getNavigationMessage(locationState: unknown): string | undefined {
  if (typeof locationState !== "object" || locationState === null) return undefined
  const message = (locationState as { message?: unknown }).message
  return typeof message === "string" ? message : undefined
}

export default function Login() {
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const role = useAuthStore((state) => state.role)
  const setSession = useAuthStore((state) => state.setSession)
  const [initialMessage] = useState(() => {
    const navigationMessage = getNavigationMessage(location.state)
    if (navigationMessage) return navigationMessage

    const sessionMessage =
      typeof window !== "undefined" ? window.sessionStorage.getItem("auth-message") : null
    if (sessionMessage) window.sessionStorage.removeItem("auth-message")
    return sessionMessage
  })

  if (role) return <Navigate to={getDefaultRouteForRole(role)} replace />

  function handleAuthenticated(user: CurrentUserResponse) {
    queryClient.clear()
    setSession(user.role, user.username, user.user_id)
    navigate(getDefaultRouteForRole(user.role), { replace: true })
  }

  return (
    <MfaLoginFlow
      initialMessage={initialMessage ?? undefined}
      onAuthenticated={handleAuthenticated}
    />
  )
}
