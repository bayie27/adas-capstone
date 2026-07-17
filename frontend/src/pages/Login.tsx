import { useEffect, useState, type FormEvent } from "react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"
import { useMutation } from "@tanstack/react-query"
import { getCurrentUser, loginUser } from "@/services/auth"
import { useAuthStore } from "@/store/useAuthStore"
import { mapApiRoleToAppRole, getDefaultRouteForRole } from "@/utils/auth"
import { getApiErrorMessage } from "@/utils/api"
import type { NoticeState } from "@/components/ui/NoticeBanner"
import { PasswordInput } from "@/components/ui/PasswordInput"

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const token = useAuthStore((state) => state.token)
  const role = useAuthStore((state) => state.role)
  const setSession = useAuthStore((state) => state.setSession)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [statusMessage, setStatusMessage] = useState<NoticeState | null>(null)

  const loginMutation = useMutation({
    mutationFn: async (credentials: { username: string; password: string }) => {
      const { access_token } = await loginUser(credentials)
      const currentUser = await getCurrentUser(access_token)
      const mappedRole = mapApiRoleToAppRole(currentUser.role)

      if (!mappedRole) {
        throw new Error("Your account role is not supported in this client.")
      }

      return { access_token, mappedRole, currentUser }
    },
    onSuccess: ({ access_token, mappedRole, currentUser }) => {
      setSession(access_token, mappedRole, currentUser.username, currentUser.user_id)
      navigate(getDefaultRouteForRole(mappedRole), { replace: true })
    },
    onError: (error) => {
      setStatusMessage({
        tone: "error",
        message: getApiErrorMessage(error, "Unable to log in. Please try again."),
      })
    },
  })

  useEffect(() => {
    // Check for message from navigation state (post-action confirmations)
    const navigationMessage = (location.state as { message?: string } | null)?.message

    if (navigationMessage) {
      setStatusMessage({ tone: "success", message: navigationMessage })
      return
    }

    // Check for message from 401 redirect (session expiry)
    const sessionMessage = typeof window !== "undefined" ? window.sessionStorage.getItem("auth-message") : null

    if (sessionMessage) {
      setStatusMessage({ tone: "error", message: sessionMessage })
      window.sessionStorage.removeItem("auth-message")
    }
  }, [location.state])

  if (token && role) {
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
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#0A0A0A] p-8">
      <div className="w-full max-w-[400px] rounded-xl border border-[#2A2A2A] bg-[#111111] p-8 shadow-2xl">
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-4 flex w-24 items-center justify-center">
            <img src="/adas-logo.png" alt="ADAS Logo" className="h-auto w-full object-contain drop-shadow-md" />
          </div>
          <h1 className="font-logo text-xl font-bold uppercase tracking-[0.3em] text-white">ADAS</h1>
          <p className="mt-1 text-center text-xs tracking-wide text-[#A1A1AA]">
            Accident Detection and Alert System
          </p>
        </div>

        <form onSubmit={handleLogin} className="space-y-5">
          <div>
            <label className="mb-1.5 block text-xs font-medium tracking-wide text-[#E4E4E7]">Username</label>
            <input
              type="text"
              placeholder="username"
              value={username}
              onChange={(e) => {
                setStatusMessage(null)
                setUsername(e.target.value)
              }}
              autoComplete="username"
              className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2.5 text-sm text-white transition-colors placeholder-[#52525B] focus:border-[#555] focus:outline-none"
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
            inputClassName="py-2.5 tracking-widest transition-colors placeholder-[#52525B]"
            toggleClassName="text-[#A1A1AA]"
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
                statusMessage.tone === "success" ? "text-emerald-400" : "text-[#F87171]"
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
