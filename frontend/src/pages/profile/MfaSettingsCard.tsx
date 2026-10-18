import { useCallback, useEffect, useRef, useState, type FormEvent } from "react"

import {
  beginMfaEnrollmentFromSession,
  beginMfaReplacement,
  cancelMfaChallenge,
  getMfaStatus,
  rotateMfaRecoveryCodes,
} from "@/api/mfa"
import type { ChallengeState, EnrollmentConfirmationResponse, MfaStatusResponse } from "@/api/mfa"
import { getApiError, suspendAuthRedirect } from "@/api/client"
import { useMfaSensitiveFlow } from "@/components/auth/mfaSensitiveFlow"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { useAuthStore } from "@/store/useAuthStore"
import { getMfaErrorMessage, getMfaRateLimitDeadline, useMfaRateLimit } from "@/pages/auth/mfaUi"
import { MfaEnrollmentPanel } from "@/pages/auth/MfaEnrollmentPanel"

type SettingsMode =
  | "status"
  | "replace-proof"
  | "rotate-proof"
  | "demo-enrollment-proof"
  | { kind: "enrollment"; challenge: ChallengeState; closesCurrentSession: boolean }

function enrolledDate(value: string | null): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return new Intl.DateTimeFormat(undefined, { dateStyle: "long" }).format(date)
}

export function MfaSettingsCard({
  onSessionRevoked,
  onSignedOut,
}: {
  onSessionRevoked: () => void
  onSignedOut: () => void
}) {
  const accountName = useAuthStore((state) => state.username) ?? "your ADAS account"
  const { showCodes } = useMfaSensitiveFlow()
  const [status, setStatus] = useState<MfaStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [mode, setMode] = useState<SettingsMode>("status")
  const [password, setPassword] = useState("")
  const [totpCode, setTotpCode] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [rateLimitDeadline, setRateLimitDeadline] = useState<string | null>(null)
  const rateLimitSeconds = useMfaRateLimit(rateLimitDeadline, setRateLimitDeadline)
  const rateLimited = rateLimitSeconds !== null && rateLimitSeconds > 0
  const submissionLock = useRef(false)
  const mounted = useRef(true)
  const redirectRelease = useRef<(() => void) | null>(null)

  const releaseAuthRedirect = useCallback(() => {
    redirectRelease.current?.()
    redirectRelease.current = null
  }, [])

  const refreshStatus = useCallback(async () => {
    try {
      const result = await getMfaStatus()
      if (mounted.current) {
        setStatus(result)
        setLoadError(null)
      }
    } catch {
      if (mounted.current) setLoadError("Unable to load authenticator status. Try again.")
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    mounted.current = true
    void getMfaStatus()
      .then((result) => {
        if (!active) return
        setStatus(result)
        setLoadError(null)
      })
      .catch(() => {
        if (active) setLoadError("Unable to load authenticator status. Try again.")
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
      mounted.current = false
      releaseAuthRedirect()
    }
  }, [releaseAuthRedirect])

  function clearProofInputs() {
    setPassword("")
    setTotpCode("")
    setError(null)
  }

  function closeForm() {
    clearProofInputs()
    setMode("status")
  }

  async function startReplacement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submissionLock.current || rateLimited || !password || !/^[0-9]{6}$/.test(totpCode)) return
    submissionLock.current = true
    setError(null)
    setIsSubmitting(true)
    try {
      const challenge = await beginMfaReplacement(password, totpCode)
      clearProofInputs()
      setMode({ kind: "enrollment", challenge, closesCurrentSession: true })
    } catch (requestError) {
      const limit = getMfaRateLimitDeadline(requestError)
      if (limit) setRateLimitDeadline(limit)
      setError(getMfaErrorMessage(requestError, "Unable to start authenticator replacement."))
      if (getApiError(requestError)?.code === "MFA_STATE_CONFLICT") void refreshStatus()
    } finally {
      submissionLock.current = false
      setIsSubmitting(false)
    }
  }

  async function rotateCodes(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submissionLock.current || rateLimited || !password || !/^[0-9]{6}$/.test(totpCode)) return
    submissionLock.current = true
    setError(null)
    setIsSubmitting(true)
    try {
      const result = await rotateMfaRecoveryCodes(password, totpCode)
      clearProofInputs()
      setMode("status")
      setStatus((current) =>
        current ? { ...current, recovery_codes_remaining: result.recovery_codes.length } : current,
      )
      showCodes({
        codes: result.recovery_codes,
        accountName,
        onAcknowledged: () => {},
      })
    } catch (requestError) {
      const limit = getMfaRateLimitDeadline(requestError)
      if (limit) setRateLimitDeadline(limit)
      setError(getMfaErrorMessage(requestError, "Unable to rotate recovery codes."))
      if (getApiError(requestError)?.code === "MFA_STATE_CONFLICT") void refreshStatus()
    } finally {
      submissionLock.current = false
      setIsSubmitting(false)
    }
  }

  async function beginDemoEnrollment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submissionLock.current || rateLimited || !password) return
    submissionLock.current = true
    setError(null)
    setIsSubmitting(true)
    try {
      const challenge = await beginMfaEnrollmentFromSession(password)
      clearProofInputs()
      setMode({ kind: "enrollment", challenge, closesCurrentSession: true })
    } catch (requestError) {
      const limit = getMfaRateLimitDeadline(requestError)
      if (limit) setRateLimitDeadline(limit)
      setError(getMfaErrorMessage(requestError, "Unable to start authenticator setup."))
      if (getApiError(requestError)?.code === "MFA_STATE_CONFLICT") void refreshStatus()
    } finally {
      submissionLock.current = false
      setIsSubmitting(false)
    }
  }

  async function cancelEnrollment() {
    releaseAuthRedirect()
    try {
      await cancelMfaChallenge()
    } catch {
      // The challenge is short-lived and idempotently cancelable.
    }
    closeForm()
    if (status?.state === "enrolled") {
      setError("Setup cancelled. Your current authenticator is still active.")
    }
  }

  function onEnrollmentCompleted(result: EnrollmentConfirmationResponse) {
    const closesCurrentSession = typeof mode === "object" && mode.closesCurrentSession
    const releaseAfterCodeDisplay = closesCurrentSession ? redirectRelease.current : null
    if (closesCurrentSession) redirectRelease.current = null
    const codes = result.recovery_codes
    if (result.status === "authenticated") {
      setStatus({
        state: "enrolled",
        recovery_codes_remaining: codes.length,
        enrolled_at: new Date().toISOString(),
        auth_method: "totp",
      })
    }
    setMode("status")
    clearProofInputs()
    showCodes({
      codes,
      accountName: result.status === "authenticated" ? result.user.username : accountName,
      onAcknowledged: () => {
        releaseAfterCodeDisplay?.()
        if (closesCurrentSession) onSignedOut()
      },
      onDismissed: releaseAfterCodeDisplay ?? undefined,
    })
    if (closesCurrentSession) onSessionRevoked()
  }

  function beginConfirmationHandoff() {
    if (redirectRelease.current === null) redirectRelease.current = suspendAuthRedirect()
  }

  if (loading) {
    return (
      <Card className="p-6">
        <p role="status" className="text-secondary text-fg-muted">
          Loading authenticator status…
        </p>
      </Card>
    )
  }

  if (loadError || !status) {
    return (
      <Card className="p-6">
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-fg">Authenticator</h2>
          <p role="alert" className="text-secondary text-danger">
            {loadError ?? "Unable to load authenticator status."}
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setLoading(true)
              setLoadError(null)
              void refreshStatus()
            }}
          >
            Retry
          </Button>
        </div>
      </Card>
    )
  }

  if (typeof mode === "object") {
    return (
      <MfaEnrollmentPanel
        challenge={mode.challenge}
        onCompleted={onEnrollmentCompleted}
        onCancel={() => void cancelEnrollment()}
        rateLimitDeadline={rateLimitDeadline}
        onRateLimitDeadlineChange={setRateLimitDeadline}
        beforeConfirm={mode.closesCurrentSession ? beginConfirmationHandoff : undefined}
        onConfirmFailed={mode.closesCurrentSession ? releaseAuthRedirect : undefined}
      />
    )
  }

  return (
    <Card className="p-6 sm:p-8">
      <div className="mb-6 space-y-2">
        <h2 className="text-lg font-semibold text-fg">Authenticator</h2>
        {status.state === "enrolled" ? (
          <>
            <p className="text-secondary text-fg-muted">
              Authenticator enabled
              {enrolledDate(status.enrolled_at)
                ? ` since ${enrolledDate(status.enrolled_at)}.`
                : "."}
            </p>
            <p className="text-caption text-fg-muted">
              {status.recovery_codes_remaining} recovery codes remaining.
            </p>
            {status.auth_method === "demo_impersonation" ? (
              <p className="text-caption text-fg-muted">
                DEMO IMPERSONATION SESSION. Security changes still require your password and current
                authenticator code.
              </p>
            ) : null}
          </>
        ) : status.state === "recovery_pending" ? (
          <p className="text-secondary text-fg-muted">
            Authenticator recovery is pending. Sign in with your password and another unused
            recovery code to set up a new authenticator.
          </p>
        ) : status.auth_method === "demo_impersonation" ? (
          <p className="text-secondary text-fg-muted">
            DEMO IMPERSONATION SESSION. This account has no authenticator yet. Verify your password
            to set one up.
          </p>
        ) : (
          <p className="text-secondary text-fg-muted">
            Authenticator setup is unavailable for this session. Sign in through the secure flow.
          </p>
        )}
      </div>

      {error ? (
        <p
          role="alert"
          className="mb-5 rounded-md border border-danger-border bg-danger-subtle px-4 py-3 text-caption text-danger"
        >
          {error}
        </p>
      ) : null}

      {status.state === "enrolled" && mode === "status" ? (
        <div className="flex flex-col gap-3 sm:flex-row">
          <Button type="button" variant="outline" onClick={() => setMode("replace-proof")}>
            Replace authenticator
          </Button>
          <Button type="button" variant="outline" onClick={() => setMode("rotate-proof")}>
            Rotate recovery codes
          </Button>
        </div>
      ) : null}

      {status.state === "unenrolled" &&
      status.auth_method === "demo_impersonation" &&
      mode === "status" ? (
        <Button type="button" onClick={() => setMode("demo-enrollment-proof")}>
          Set up authenticator
        </Button>
      ) : null}

      {mode === "replace-proof" || mode === "rotate-proof" ? (
        <form
          onSubmit={mode === "replace-proof" ? startReplacement : rotateCodes}
          className="max-w-sm space-y-5"
        >
          <PasswordInput
            label={mode === "replace-proof" ? "Current password" : "Password"}
            value={password}
            autoComplete="current-password"
            maxLength={128}
            disabled={isSubmitting || rateLimited}
            onChange={(value) => {
              setPassword(value)
              if (!rateLimited) setError(null)
            }}
          />
          <Input
            label="Current authenticator code"
            value={totpCode}
            onChange={(event) => {
              const next = event.target.value
              if (!/^[0-9]{0,6}$/.test(next)) return
              setTotpCode(next)
              if (!rateLimited) setError(null)
            }}
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            disabled={isSubmitting || rateLimited}
          />
          {rateLimited ? (
            <p role="status" className="text-caption text-warning" aria-live="polite">
              Wait {rateLimitSeconds}s before trying again.
            </p>
          ) : null}
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              type="submit"
              isLoading={isSubmitting}
              loadingLabel={mode === "replace-proof" ? "Starting…" : "Rotating…"}
              disabled={rateLimited || !password || !/^[0-9]{6}$/.test(totpCode)}
            >
              {rateLimited
                ? `Try again in ${rateLimitSeconds}s`
                : mode === "replace-proof"
                  ? "Start replacement"
                  : "Rotate codes"}
            </Button>
            <Button type="button" variant="ghost" disabled={isSubmitting} onClick={closeForm}>
              Cancel
            </Button>
          </div>
          {mode === "replace-proof" ? (
            <p className="text-caption text-fg-muted">
              Your current authenticator stays active until the replacement is confirmed.
            </p>
          ) : (
            <p className="text-caption text-fg-muted">
              Rotation replaces every unused recovery code and keeps your current session active.
            </p>
          )}
        </form>
      ) : null}

      {mode === "demo-enrollment-proof" ? (
        <form onSubmit={beginDemoEnrollment} className="max-w-sm space-y-5">
          <PasswordInput
            label="Password"
            value={password}
            autoComplete="current-password"
            maxLength={128}
            disabled={isSubmitting || rateLimited}
            onChange={(value) => {
              setPassword(value)
              if (!rateLimited) setError(null)
            }}
          />
          {rateLimited ? (
            <p role="status" className="text-caption text-warning" aria-live="polite">
              Wait {rateLimitSeconds}s before trying again.
            </p>
          ) : null}
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              type="submit"
              isLoading={isSubmitting}
              loadingLabel="Starting…"
              disabled={rateLimited || !password}
            >
              {rateLimited ? `Try again in ${rateLimitSeconds}s` : "Continue setup"}
            </Button>
            <Button type="button" variant="ghost" disabled={isSubmitting} onClick={closeForm}>
              Cancel
            </Button>
          </div>
        </form>
      ) : null}
    </Card>
  )
}
