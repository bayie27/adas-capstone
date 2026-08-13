import { useState, type FormEvent } from "react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"
import { useMutation } from "@tanstack/react-query"
import { loginUser } from "@/services/auth"
import { useAuthStore } from "@/store/useAuthStore"
import { mapApiRoleToAppRole, getDefaultRouteForRole } from "@/utils/auth"
import { getApiErrorMessage } from "@/utils/api"
import type { NoticeState } from "@/components/ui/NoticeBanner"
import { PasswordInput } from "@/components/ui/PasswordInput"

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
      const mappedRole = mapApiRoleToAppRole(currentUser.role)

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
      <div className="w-full max-w-[400px] rounded-xl border border-stroke bg-surface-1 p-8 shadow-2xl">
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-4 flex w-24 items-center justify-center">
            <img
              src="/adas-logo.png"
              alt="ADAS Logo"
              className="h-auto w-full object-contain drop-shadow-md"
            />
          </div>
          <h1 className="font-logo text-xl font-bold uppercase tracking-[0.3em] text-white">
            ADAS
          </h1>
          <p className="mt-1 text-center text-xs tracking-wide text-fg-muted">
            Accident Detection and Alert System
          </p>
        </div>

        <form onSubmit={handleLogin} className="space-y-5">
          <div>
            <label className="mb-1.5 block text-xs font-medium tracking-wide text-fg-body">
              Username
            </label>
            <input
              type="text"
              placeholder="username"
              value={username}
              onChange={(e) => {
                setStatusMessage(null)
                setUsername(e.target.value)
              }}
              autoComplete="username"
              className="w-full rounded-md border border-stroke bg-surface-1 px-3 py-2.5 text-sm text-white transition-colors placeholder-fg-muted focus:border-stroke-strong focus:outline-none"
            />
          </div>
          <PasswordInput
            label="Password"
            value={password}
            onChange={(value) => {
              setStatusMessage(null)
              setPassword(value)
            }}
            autoComplete="current-password"
            placeholder="password"
            labelClassName="mb-1.5 text-xs font-medium tracking-wide"
            inputClassName="py-2.5 tracking-widest transition-colors placeholder-fg-muted"
            toggleClassName="text-fg-muted"
            iconSize={18}
          />
          <button
            type="submit"
            disabled={loginMutation.isPending}
            className="mt-2 w-full rounded-md bg-white py-2.5 text-sm font-semibold text-black transition-colors hover:bg-gray-100"
          >
            {loginMutation.isPending ? "Signing in..." : "Login"}
          </button>
          {statusMessage ? (
            <p
              className={`text-center text-xs ${
                statusMessage.tone === "success" ? "text-emerald-400" : "text-danger"
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
