import { create } from "zustand"

import type { AppUserRole } from "@/types/auth"

const AUTH_STORAGE_KEY = "adas-auth-session"
const VALID_ROLES = ["Administrator", "Operator"] as const

type StoredAuthSession = {
  role: AppUserRole | null
  username: string | null
  userId: number | null
}

function isValidRole(value: unknown): value is AppUserRole {
  return typeof value === "string" && VALID_ROLES.includes(value as AppUserRole)
}

interface AuthState {
  role: AppUserRole | null
  username: string | null
  userId: number | null
  setSession: (role: AppUserRole, username: string, userId: number) => void
  clearSession: () => void
}

function createEmptySession(): StoredAuthSession {
  return {
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

    const username = typeof parsed.username === "string" ? parsed.username : null
    const userId = typeof parsed.userId === "number" ? parsed.userId : null
    const role = isValidRole(parsed.role) ? parsed.role : null

    return { role, username, userId }
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
  if (!session.role || !session.username) {
    storage.removeItem(AUTH_STORAGE_KEY)
    return
  }

  storage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
}

const initialSession = readStoredSession()

// P2 (D-006): the session credential is an HttpOnly cookie invisible to
// JavaScript — there is no token to hold here. role/username/userId are a
// *display cache* for instant UI rendering, not proof of authentication;
// every actual request is authenticated by the cookie the browser attaches
// automatically, and the backend is the sole authority on session validity.
export const useAuthStore = create<AuthState>((set) => ({
  role: initialSession.role,
  username: initialSession.username,
  userId: initialSession.userId,
  setSession: (role, username, userId) => {
    writeStoredSession({ role, username, userId })
    set({ role, username, userId })
  },
  clearSession: () => {
    const emptySession = createEmptySession()
    writeStoredSession(emptySession)
    set(emptySession)
  },
}))
