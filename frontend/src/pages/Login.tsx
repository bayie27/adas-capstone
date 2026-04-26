import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import EyeOffLineIcon from "remixicon-react/EyeOffLineIcon"
import EyeLineIcon from "remixicon-react/EyeLineIcon"
import { useAuthStore } from "@/store/useAuthStore"

export default function Login() {
  const navigate = useNavigate()
  const setSession = useAuthStore((state) => state.setSession)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)

  const handleLogin = (e: FormEvent) => {
    e.preventDefault()

    const normalizedUsername = username.trim()
    const role =
      normalizedUsername === "admin" || normalizedUsername === "administrator"
        ? "Administrator"
        : "Operator"

    setSession("mock-session-token", role, normalizedUsername || "operator")
    navigate(role === "Administrator" ? "/admin" : "/user")
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
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2.5 text-sm text-white transition-colors placeholder-[#52525B] focus:border-[#555] focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium tracking-wide text-[#E4E4E7]">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                placeholder="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2.5 pr-10 text-sm tracking-widest text-white transition-colors placeholder-[#52525B] focus:border-[#555] focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#A1A1AA] transition-colors hover:text-white"
              >
                {showPassword ? <EyeLineIcon size={18} /> : <EyeOffLineIcon size={18} />}
              </button>
            </div>
          </div>
          <button
            type="submit"
            className="mt-2 w-full rounded-md bg-white py-2.5 text-sm font-semibold text-black transition-colors hover:bg-gray-100"
          >
            Login
          </button>
        </form>
      </div>
    </div>
  )
}
