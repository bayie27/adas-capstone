import { create } from "zustand"

import type { AppUserRole } from "@/types/auth"

const AUTH_STORAGE_KEY = "adas-auth-session"

type StoredAuthSession = {
  token: string | null
  role: AppUserRole | null
  username: string | null
  userId: number | null
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

    return JSON.parse(rawSession) as StoredAuthSession
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
