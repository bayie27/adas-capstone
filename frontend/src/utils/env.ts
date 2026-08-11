export function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "")
}

export function getBrowserHostname() {
  if (typeof window === "undefined") {
    return "localhost"
  }

  return window.location.hostname || "localhost"
}

export function getBrowserProtocol() {
  if (typeof window === "undefined") {
    return "http:"
  }

  return window.location.protocol || "http:"
}

function getDefaultApiBaseUrl() {
  return `${getBrowserProtocol()}//${getBrowserHostname()}:8000/api`
}

function getDefaultWsBaseUrl() {
  const wsProtocol = getBrowserProtocol() === "https:" ? "wss:" : "ws:"
  return `${wsProtocol}//${getBrowserHostname()}:8000`
}

export const API_BASE_URL = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL ?? getDefaultApiBaseUrl(),
)
export const WS_BASE_URL = trimTrailingSlash(
  import.meta.env.VITE_WS_BASE_URL ?? getDefaultWsBaseUrl(),
)
