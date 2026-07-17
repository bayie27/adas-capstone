import { create } from "zustand"

import type { AppUserRole } from "@/types/auth"

const AUTH_STORAGE_KEY = "adas-auth-session"
const VALID_ROLES = ["Administrator", "Operator"] as const

type StoredAuthSession = {
  token: string | null
  role: AppUserRole | null
  username: string | null
  userId: number | null
}

function isValidRole(value: unknown): value is AppUserRole {
  return typeof value === "string" && VALID_ROLES.includes(value as AppUserRole)
}

function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split(".")
    if (parts.length !== 3) return true

    const payload = JSON.parse(atob(parts[1]))
    const exp = payload.exp

    if (typeof exp !== "number") return true

    return Date.now() >= exp * 1000
  } catch {
    return true
  }
}

interface AuthState {
  token: string | null
  role: AppUserRole | null
  username: string | null
  userId: number | null
  setSession: (token: string, role: AppUserRole, username: string, userId: number) => void
  clearSession: () => void
}

function createEmptySession(): StoredAuthSession {
  return {
    token: null,
    role: null,
    username: null,
    userId: null,
  }
}

function getAuthStorage() {
  if (typeof window === "undefined") {
    return null
  }

  return window.localStorage
}

function readStoredSession(): StoredAuthSession {
  const storage = getAuthStorage()

  if (!storage) {
    return createEmptySession()
  }

  try {
    const rawSession = storage.getItem(AUTH_STORAGE_KEY)

    if (!rawSession) {
      return createEmptySession()
    }

    const parsed = JSON.parse(rawSession)

    // Validate stored session shape
    if (typeof parsed !== "object" || parsed === null) {
      return createEmptySession()
    }

    const token = typeof parsed.token === "string" ? parsed.token : null
    const username = typeof parsed.username === "string" ? parsed.username : null
    const userId = typeof parsed.userId === "number" ? parsed.userId : null
    const role = isValidRole(parsed.role) ? parsed.role : null

    // If token is present, check expiration
    if (token && isTokenExpired(token)) {
      return createEmptySession()
    }

    return { token, role, username, userId }
  } catch {
    return createEmptySession()
  }
}

function writeStoredSession(session: StoredAuthSession) {
  const storage = getAuthStorage()

  if (!storage) {
    return
  }

  // Partial auth state is treated as logged out so route guards and API auth stay in sync.
  if (!session.token || !session.role || !session.username) {
    storage.removeItem(AUTH_STORAGE_KEY)
    return
  }

  storage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
}

const initialSession = readStoredSession()

export const useAuthStore = create<AuthState>((set) => ({
  token: initialSession.token,
  role: initialSession.role,
  username: initialSession.username,
  userId: initialSession.userId,
  setSession: (token, role, username, userId) => {
    writeStoredSession({ token, role, username, userId })
    set({ token, role, username, userId })
  },
  clearSession: () => {
    const emptySession = createEmptySession()
    writeStoredSession(emptySession)
    set(emptySession)
  },
}))
