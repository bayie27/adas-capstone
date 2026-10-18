import { useEffect, useRef, useState, type FormEvent } from "react"

import { verifyMfaChallenge } from "@/api/mfa"
import type { ChallengeState, ChallengeVerificationResponse } from "@/api/mfa"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"
import { useNow } from "@/hooks/useNow"
import { secondsUntil } from "@/utils/format"
import {
  formatMfaDuration,
  getMfaErrorMessage,
  getMfaRateLimitDeadline,
  useMfaRateLimit,
} from "./mfaUi"

interface MfaChallengePanelProps {
  challenge: ChallengeState
  onCompleted: (result: ChallengeVerificationResponse) => void
  onCancel: (reason?: "expired" | "cancelled") => void
  rateLimitDeadline?: string | null
  onRateLimitDeadlineChange?: (deadline: string | null) => void
}

export function MfaChallengePanel({
  challenge,
  onCompleted,
  onCancel,
  rateLimitDeadline: sharedDeadline,
  onRateLimitDeadlineChange,
}: MfaChallengePanelProps) {
  const [method, setMethod] = useState<"totp" | "recovery">(
    challenge.purpose === "recovery_verify" ? "recovery" : "totp",
  )
  const [code, setCode] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [localDeadline, setLocalDeadline] = useState<string | null>(null)
  const deadline = sharedDeadline === undefined ? localDeadline : sharedDeadline
  const setDeadline = (next: string | null) => {
    if (sharedDeadline === undefined) setLocalDeadline(next)
    onRateLimitDeadlineChange?.(next)
  }
  const secondsLeftOnLimit = useMfaRateLimit(deadline, setDeadline)
  const rateLimited = secondsLeftOnLimit !== null && secondsLeftOnLimit > 0
  const now = useNow(true, 1000)
  const challengeSeconds = secondsUntil(challenge.expires_at, now)
  const expiryHandledRef = useRef(false)

  useEffect(() => {
    if (challengeSeconds === 0 && !expiryHandledRef.current) {
      expiryHandledRef.current = true
      onCancel("expired")
    }
  }, [challengeSeconds, onCancel])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting || rateLimited || challengeSeconds === 0 || !code.trim()) return

    setError(null)
    setIsSubmitting(true)
    try {
      const result = await verifyMfaChallenge(method, code.trim())
      setCode("")
      onCompleted(result)
    } catch (requestError) {
      const nextLimit = getMfaRateLimitDeadline(requestError)
      if (nextLimit) setDeadline(nextLimit)
      const message = getMfaErrorMessage(requestError, "We couldn't verify that code. Try again.")
      setError(message)
      if (message === "This security flow expired or changed. Sign in again.") {
        onCancel("expired")
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Card className="w-full max-w-[440px] p-6 sm:p-8">
      <div className="mb-6 space-y-2">
        <h1 className="text-xl font-semibold text-fg">Verify your sign-in</h1>
        <p className="text-secondary text-fg-muted">
          Enter the six-digit code from your authenticator app. Recovery codes are single-use.
        </p>
        <p className="text-caption text-fg-muted" aria-live="polite">
          {challengeSeconds !== null && challengeSeconds > 0
            ? `This sign-in request expires in ${formatMfaDuration(challengeSeconds)}.`
            : "This sign-in request has expired."}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {challenge.purpose !== "recovery_verify" ? (
          <div className="flex gap-2" aria-label="Verification method">
            <Button
              type="button"
              variant={method === "totp" ? "secondary" : "outline"}
              aria-pressed={method === "totp"}
              onClick={() => {
                setMethod("totp")
                setCode("")
                setError(null)
              }}
            >
              Use an authenticator code
            </Button>
            <Button
              type="button"
              variant={method === "recovery" ? "secondary" : "outline"}
              aria-pressed={method === "recovery"}
              onClick={() => {
                setMethod("recovery")
                setCode("")
                setError(null)
              }}
            >
              Use a recovery code
            </Button>
          </div>
        ) : null}

        <Input
          label={method === "totp" ? "Authenticator code" : "Recovery code"}
          value={code}
          autoFocus
          onChange={(event) => {
            const next = event.target.value
            if (method === "totp" && !/^[0-9]*$/.test(next)) return
            setCode(next)
            setError(null)
          }}
          type="text"
          inputMode={method === "totp" ? "numeric" : "text"}
          autoComplete={method === "totp" ? "one-time-code" : "off"}
          maxLength={method === "totp" ? 6 : 64}
          spellCheck={false}
          disabled={isSubmitting || challengeSeconds === 0}
          error={error ?? undefined}
        />

        {rateLimited ? (
          <p role="status" className="text-caption text-warning" aria-live="polite">
            Wait {secondsLeftOnLimit}s before trying another code.
          </p>
        ) : null}

        <div className="flex flex-col gap-3">
          <Button
            type="submit"
            className="w-full"
            isLoading={isSubmitting}
            loadingLabel="Verifying…"
            disabled={rateLimited || challengeSeconds === 0 || !code.trim()}
          >
            {rateLimited ? `Try again in ${secondsLeftOnLimit}s` : "Verify code"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            disabled={isSubmitting}
            onClick={() => onCancel("cancelled")}
          >
            Cancel and start over
          </Button>
        </div>
      </form>
    </Card>
  )
}
