import { QRCodeSVG } from "qrcode.react"
import { useEffect, useRef, useState, type FormEvent } from "react"

import { confirmMfaEnrollment, getMfaEnrollment } from "@/api/mfa"
import type {
  ChallengeState,
  EnrollmentConfirmationResponse,
  EnrollmentStartResponse,
} from "@/api/mfa"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { useNow } from "@/hooks/useNow"
import { secondsUntil } from "@/utils/format"
import { getApiError } from "@/api/client"
import {
  formatMfaDuration,
  getMfaErrorMessage,
  getMfaRateLimitDeadline,
  useMfaRateLimit,
} from "./mfaUi"

interface MfaEnrollmentPanelProps {
  challenge: ChallengeState
  onCompleted: (result: EnrollmentConfirmationResponse) => void
  onCancel: (reason?: "expired" | "cancelled") => void
  rateLimitDeadline?: string | null
  onRateLimitDeadlineChange?: (deadline: string | null) => void
  beforeConfirm?: () => void
  onConfirmFailed?: () => void
}

export function MfaEnrollmentPanel({
  challenge,
  onCompleted,
  onCancel,
  rateLimitDeadline: sharedDeadline,
  onRateLimitDeadlineChange,
  beforeConfirm,
  onConfirmFailed,
}: MfaEnrollmentPanelProps) {
  const [provisioning, setProvisioning] = useState<EnrollmentStartResponse | null>(null)
  const [loadingProvisioning, setLoadingProvisioning] = useState(true)
  const [loadError, setLoadError] = useState<unknown>(null)
  const [code, setCode] = useState("")
  const [confirmationError, setConfirmationError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const submissionLock = useRef(false)
  const [localDeadline, setLocalDeadline] = useState<string | null>(null)
  const deadline = sharedDeadline === undefined ? localDeadline : sharedDeadline
  const setDeadline = (next: string | null) => {
    if (sharedDeadline === undefined) setLocalDeadline(next)
    onRateLimitDeadlineChange?.(next)
  }
  const limitSecondsLeft = useMfaRateLimit(deadline, setDeadline)
  const rateLimited = limitSecondsLeft !== null && limitSecondsLeft > 0
  const now = useNow(true, 1000)
  const challengeSeconds = secondsUntil(challenge.expires_at, now)
  const cancelRef = useRef(onCancel)
  const expiryHandledRef = useRef(false)

  useEffect(() => {
    cancelRef.current = onCancel
  }, [onCancel])

  useEffect(() => {
    let active = true
    void getMfaEnrollment()
      .then((result) => {
        if (active) setProvisioning(result)
      })
      .catch((error: unknown) => {
        if (!active) return
        setLoadError(error)
        if (getApiError(error)?.code === "MFA_CHALLENGE_INVALID") cancelRef.current("expired")
      })
      .finally(() => {
        if (active) setLoadingProvisioning(false)
      })

    return () => {
      active = false
    }
  }, [challenge.purpose, challenge.expires_at])

  useEffect(() => {
    if (challengeSeconds === 0 && !expiryHandledRef.current) {
      expiryHandledRef.current = true
      cancelRef.current("expired")
    }
  }, [challengeSeconds])

  async function loadProvisioning() {
    setLoadingProvisioning(true)
    setLoadError(null)
    try {
      setProvisioning(await getMfaEnrollment())
    } catch (error) {
      setLoadError(error)
      if (getApiError(error)?.code === "MFA_CHALLENGE_INVALID") onCancel("expired")
    } finally {
      setLoadingProvisioning(false)
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (
      submissionLock.current ||
      isSubmitting ||
      rateLimited ||
      challengeSeconds === 0 ||
      !/^[0-9]{6}$/.test(code)
    )
      return

    submissionLock.current = true
    setConfirmationError(null)
    setIsSubmitting(true)
    try {
      beforeConfirm?.()
      const result = await confirmMfaEnrollment(code)
      setCode("")
      setProvisioning(null)
      onCompleted(result)
    } catch (error) {
      onConfirmFailed?.()
      const nextLimit = getMfaRateLimitDeadline(error)
      if (nextLimit) setDeadline(nextLimit)
      const message = getMfaErrorMessage(error, "We couldn't confirm that code. Try again.")
      setConfirmationError(message)
      if (getApiError(error)?.code === "MFA_CHALLENGE_INVALID") onCancel("expired")
    } finally {
      submissionLock.current = false
      setIsSubmitting(false)
    }
  }

  return (
    <Card className="w-full max-w-[560px] p-6 sm:p-8">
      <div className="mb-6 space-y-2">
        <h1 className="text-xl font-semibold text-fg">Set up your authenticator</h1>
        <p className="text-secondary text-fg-muted">
          Use a local authenticator app to scan this QR code, then enter its current six-digit code.
          Turn off cloud sync for this authenticator.
        </p>
        <p className="text-caption text-fg-muted" aria-live="polite">
          Setup expires in {formatMfaDuration(Math.max(0, challengeSeconds ?? 0))}. Starting over
          will not extend the server deadline.
        </p>
      </div>

      {loadingProvisioning ? (
        <p role="status" className="py-8 text-center text-secondary text-fg-muted">
          Loading authenticator setup…
        </p>
      ) : loadError ? (
        <QueryErrorBanner
          error={loadError}
          fallback="Unable to load authenticator setup."
          onRetry={() => void loadProvisioning()}
        />
      ) : provisioning ? (
        <div className="space-y-6">
          <div className="flex flex-col items-center gap-4 rounded-md border border-stroke bg-surface-2 p-5">
            <QRCodeSVG
              value={provisioning.provisioning_uri}
              title="Authenticator setup QR code"
              size={240}
              level="M"
              marginSize={4}
              bgColor="var(--color-surface-1)"
              fgColor="var(--color-fg)"
              className="h-auto w-full max-w-[240px]"
            />
            <div className="w-full space-y-1 text-center">
              <p className="text-caption text-fg-muted">
                {provisioning.issuer} · {provisioning.account_name}
              </p>
              <p className="text-caption font-medium text-fg">Can&apos;t scan? Enter this key:</p>
              <code className="block break-all rounded bg-surface-1 px-3 py-2 text-secondary font-semibold tracking-[0.08em] text-fg">
                {provisioning.manual_key}
              </code>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <Input
              label="Authenticator code"
              value={code}
              autoFocus
              onChange={(event) => {
                const next = event.target.value
                if (!/^[0-9]{0,6}$/.test(next)) return
                setCode(next)
                setConfirmationError(null)
              }}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              spellCheck={false}
              disabled={isSubmitting || challengeSeconds === 0}
              error={confirmationError ?? undefined}
              hint="Use the code currently shown in your authenticator app. If you just used a code, wait for the next one."
            />

            {rateLimited ? (
              <p role="status" className="text-caption text-warning" aria-live="polite">
                Wait {limitSecondsLeft}s before trying another code.
              </p>
            ) : null}

            <div className="flex flex-col gap-3">
              <Button
                type="submit"
                className="w-full"
                isLoading={isSubmitting}
                loadingLabel="Confirming…"
                disabled={rateLimited || challengeSeconds === 0 || code.length !== 6}
              >
                {rateLimited ? `Try again in ${limitSecondsLeft}s` : "Confirm authenticator"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                disabled={isSubmitting}
                onClick={() => onCancel("cancelled")}
              >
                Cancel setup
              </Button>
            </div>
          </form>
        </div>
      ) : null}
    </Card>
  )
}
