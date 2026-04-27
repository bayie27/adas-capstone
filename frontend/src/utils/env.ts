function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "")
}

function getBrowserHostname() {
  if (typeof window === "undefined") {
    return "localhost"
  }

  return window.location.hostname || "localhost"
}

function getDefaultApiBaseUrl() {
  return `http://${getBrowserHostname()}:8000/api`
}

function getDefaultWsBaseUrl() {
  return `ws://${getBrowserHostname()}:8000`
}

export const API_BASE_URL = trimTrailingSlash(import.meta.env.VITE_API_BASE_URL ?? getDefaultApiBaseUrl())
export const WS_BASE_URL = trimTrailingSlash(import.meta.env.VITE_WS_BASE_URL ?? getDefaultWsBaseUrl())
