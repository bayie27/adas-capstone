function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "")
}

export const API_BASE_URL = trimTrailingSlash(import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api")
export const WS_BASE_URL = trimTrailingSlash(import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000")
