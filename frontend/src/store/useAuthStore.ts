import { create } from "zustand"

const AUTH_STORAGE_KEY = "adas-auth-session"

interface AuthState {
  token: string | null
  role: "Administrator" | "Operator" | null
  username: string | null
  setSession: (token: string, role: "Administrator" | "Operator", username: string) => void
  clearSession: () => void
}

interface StoredAuthSession {
  token: string | null
  role: AuthState["role"]
  username: string | null
}

function emptySession(): StoredAuthSession {
  return { token: null, role: null, username: null }
}

function readStoredSession(): StoredAuthSession {
  if (typeof window === "undefined") {
    return emptySession()
  }

  try {
    const rawSession = window.localStorage.getItem(AUTH_STORAGE_KEY)

    if (!rawSession) {
      return emptySession()
    }

    return JSON.parse(rawSession) as StoredAuthSession
  } catch {
    return emptySession()
  }
}

function writeStoredSession(session: StoredAuthSession) {
  if (typeof window === "undefined") {
    return
  }

  if (!session.token || !session.role || !session.username) {
    window.localStorage.removeItem(AUTH_STORAGE_KEY)
    return
  }

  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
}

const initialSession = readStoredSession()

export const useAuthStore = create<AuthState>((set) => ({
  token: initialSession.token,
  role: initialSession.role,
  username: initialSession.username,
  setSession: (token, role, username) => {
    writeStoredSession({ token, role, username })
    set({ token, role, username })
  },
  clearSession: () => {
    writeStoredSession(emptySession())
    set(emptySession())
  },
}))
