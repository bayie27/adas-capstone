import { useState, type FormEvent } from "react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"
import { useMutation } from "@tanstack/react-query"
import { loginUser } from "@/api/auth"
import { useAuthStore } from "@/store/useAuthStore"
import { toApiRole, getDefaultRouteForRole } from "@/utils/auth"
import { getApiErrorMessage } from "@/api/client"
import type { NoticeState } from "@/components/ui/NoticeBanner"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"

function getNavigationMessage(locationState: unknown): string | undefined {
  return (locationState as { message?: string } | null)?.message
}

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const role = useAuthStore((state) => state.role)
  const setSession = useAuthStore((state) => state.setSession)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  // Initialize from a one-time "post-action confirmation" message passed via
  // router navigation state, or else a session-expiry message left behind by
  // a 401 redirect. Reading/consuming that one-shot data during the lazy
  // initializer means it's visible on the very first paint, and the
  // sessionStorage entry is consumed exactly once (idempotent to repeat).
  const [statusMessage, setStatusMessage] = useState<NoticeState | null>(() => {
    const navigationMessage = getNavigationMessage(location.state)

    if (navigationMessage) {
      return { tone: "success", message: navigationMessage }
    }

    const sessionMessage =
      typeof window !== "undefined" ? window.sessionStorage.getItem("auth-message") : null

    if (sessionMessage) {
      window.sessionStorage.removeItem("auth-message")
      return { tone: "error", message: sessionMessage }
    }

    return null
  })

  const loginMutation = useMutation({
    mutationFn: async (credentials: { username: string; password: string }) => {
      const { user: currentUser } = await loginUser(credentials)
      const mappedRole = toApiRole(currentUser.role)

      if (!mappedRole) {
        throw new Error("Your account role is not supported in this client.")
      }

      return { mappedRole, currentUser }
    },
    onSuccess: ({ mappedRole, currentUser }) => {
      setSession(mappedRole, currentUser.username, currentUser.user_id)
      navigate(getDefaultRouteForRole(mappedRole), { replace: true })
    },
    onError: (error) => {
      setStatusMessage({
        tone: "error",
        message: getApiErrorMessage(error, "Unable to log in. Please try again."),
      })
    },
  })

  // The lazy initializer above only runs once (on mount). If the router ever
  // hands this already-mounted component a new location.state identity (e.g.
  // navigating back to /login again with a fresh confirmation message),
  // re-derive the message during render rather than in an effect.
  const [prevLocationState, setPrevLocationState] = useState(location.state)

  if (location.state !== prevLocationState) {
    setPrevLocationState(location.state)

    const navigationMessage = getNavigationMessage(location.state)

    if (navigationMessage) {
      setStatusMessage({ tone: "success", message: navigationMessage })
    }
  }

  if (role) {
    return <Navigate to={getDefaultRouteForRole(role)} replace />
  }

  const handleLogin = (e: FormEvent) => {
    e.preventDefault()

    const normalizedUsername = username.trim()

    if (!normalizedUsername || !password) {
      setStatusMessage({ tone: "error", message: "Enter both username and password." })
      return
    }

    setStatusMessage(null)
    loginMutation.mutate({ username: normalizedUsername, password })
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-canvas p-8">
      <div className="w-full max-w-[400px] rounded-xl border border-stroke bg-surface-1 p-8 shadow-overlay">
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-4 flex w-24 items-center justify-center">
            <img
              src="/adas-logo.png"
              alt="ADAS Logo"
              className="h-auto w-full object-contain drop-shadow-md"
            />
          </div>
          <h1 className="text-xl font-bold uppercase tracking-[0.25em] text-fg">ADAS</h1>
          <p className="mt-1 text-center text-xs tracking-wide text-fg-muted">
            Accident Detection and Alert System
          </p>
        </div>

        <form onSubmit={handleLogin} className="space-y-5">
          <Input
            label="Username"
            type="text"
            placeholder="username"
            value={username}
            onChange={(event) => {
              setStatusMessage(null)
              setUsername(event.target.value)
            }}
            autoComplete="username"
          />
          <PasswordInput
            label="Password"
            value={password}
            onChange={(value) => {
              setStatusMessage(null)
              setPassword(value)
            }}
            autoComplete="current-password"
            placeholder="password"
            iconSize={18}
            // PasswordInput still carries the pre-Phase-4 geometry so the three
            // password modals do not move; the login card is rebuilt to the
            // frame, so it opts back into Input's 40px §2.3 control height and
            // matches the username field above it.
            inputClassName="h-10 px-4 py-0 text-secondary"
          />
          <Button
            type="submit"
            className="mt-2 w-full"
            isLoading={loginMutation.isPending}
            loadingLabel="Signing in…"
          >
            Login
          </Button>
          {statusMessage ? (
            <p
              className={`text-center text-caption ${
                statusMessage.tone === "success" ? "text-success" : "text-danger"
              }`}
            >
              {statusMessage.message}
            </p>
          ) : null}
        </form>
      </div>
    </div>
  )
}
