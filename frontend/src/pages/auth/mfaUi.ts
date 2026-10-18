import axios from "axios"
import { useEffect } from "react"

import { getApiError } from "@/api/client"
import { useNow } from "@/hooks/useNow"
import { correctedNowMs } from "@/utils/datetime"
import { secondsUntil } from "@/utils/format"

export const MFA_RATE_LIMIT_FALLBACK_SECONDS = 60

export function getMfaRateLimitDeadline(error: unknown): string | null {
  if (getApiError(error)?.code !== "AUTH_RATE_LIMITED") return null

  let seconds = MFA_RATE_LIMIT_FALLBACK_SECONDS
  if (axios.isAxiosError(error)) {
    const header = error.response?.headers?.["retry-after"]
    const parsed = Number(header)
    if (header !== undefined && Number.isFinite(parsed) && parsed > 0) {
      seconds = parsed
    }
  }

  return new Date(correctedNowMs() + seconds * 1000).toISOString()
}

export function getMfaErrorMessage(error: unknown, fallback: string): string {
  switch (getApiError(error)?.code) {
    case "AUTH_INVALID_CREDENTIALS":
    case "MFA_INVALID_CODE":
      return "We couldn't verify your credentials. Check the password or code and try again."
    case "AUTH_RATE_LIMITED":
      return "Too many attempts. Wait for the countdown before trying again."
    case "MFA_STATE_CONFLICT":
      return "Your security status changed. Refresh this section and start again."
    case "MFA_CHALLENGE_INVALID":
      return "This security flow expired or changed. Sign in again."
    default:
      return fallback
  }
}

export function useMfaRateLimit(
  deadline: string | null,
  onDeadlineChange: (deadline: string | null) => void,
): number | null {
  const now = useNow(deadline !== null, 1000)
  const seconds = secondsUntil(deadline, now)

  useEffect(() => {
    if (deadline !== null && seconds === 0) onDeadlineChange(null)
  }, [deadline, onDeadlineChange, seconds])

  return seconds
}

export function challengeSecondsLeft(expiresAt: string): number {
  return Math.max(0, Math.ceil((Date.parse(expiresAt) - correctedNowMs()) / 1000))
}

export function formatMfaDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 60 * 60) {
    const minutes = Math.floor(seconds / 60)
    return `${minutes}m ${seconds % 60}s`
  }
  if (seconds < 24 * 60 * 60) {
    const hours = Math.floor(seconds / 3600)
    return `${hours}h ${Math.floor((seconds % 3600) / 60)}m`
  }
  const days = Math.floor(seconds / 86400)
  return `${days}d ${Math.floor((seconds % 86400) / 3600)}h`
}
