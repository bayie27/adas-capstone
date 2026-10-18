import { useEffect, useState, type FormEvent } from "react"

import {
  beginMfaLogin,
  cancelMfaChallenge,
  getMfaChallenge,
  type ChallengeState,
  type CompletedLogin,
  type EnrollmentConfirmationResponse,
} from "@/api/mfa"
import type { CurrentUserResponse, LoginCredentials } from "@/api/auth"
import { getApiError } from "@/api/client"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { getMfaErrorMessage, getMfaRateLimitDeadline, useMfaRateLimit } from "./mfaUi"
import { MfaChallengePanel } from "./MfaChallengePanel"
import { MfaEnrollmentPanel } from "./MfaEnrollmentPanel"
import { RecoveryCodesPanel } from "./RecoveryCodesPanel"

type FlowState =
  | { kind: "checking" }
  | { kind: "password" }
  | { kind: "challenge"; challenge: ChallengeState }
  | { kind: "enrollment"; challenge: ChallengeState }
  | {
      kind: "codes"
      codes: string[]
      accountName: string
      user: CurrentUserResponse | null
    }

function stateForChallenge(challenge: ChallengeState): FlowState {
  return challenge.status === "enrollment_required"
    ? { kind: "enrollment", challenge }
    : { kind: "challenge", challenge }
}

export function MfaLoginFlow({
  onAuthenticated,
  initialMessage,
}: {
  onAuthenticated: (user: CurrentUserResponse) => void
  initialMessage?: string
}) {
  const [flow, setFlow] = useState<FlowState>({ kind: "checking" })
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [message, setMessage] = useState<string | null>(initialMessage ?? null)
  const [rateLimitDeadline, setRateLimitDeadline] = useState<string | null>(null)
  const secondsLeft = useMfaRateLimit(rateLimitDeadline, setRateLimitDeadline)
  const rateLimited = secondsLeft !== null && secondsLeft > 0

  useEffect(() => {
    let active = true
    void getMfaChallenge()
      .then((challenge) => {
        if (active) setFlow(stateForChallenge(challenge))
      })
      .catch((error: unknown) => {
        if (!active) return
        if (getApiError(error)?.code === "MFA_CHALLENGE_INVALID") {
          setMessage("Your previous sign-in request expired. Enter your password again.")
        } else {
          setMessage(
            "Couldn't check for an active sign-in. You can start again with your password.",
          )
        }
        setFlow({ kind: "password" })
      })

    return () => {
      active = false
    }
  }, [])

  async function cancelFlow(reason: "expired" | "cancelled" = "cancelled") {
    try {
      await cancelMfaChallenge()
    } catch {
      // Cancel is idempotent on the server. A fresh password stage supersedes
      // a challenge even if this best-effort cookie cleanup cannot complete.
    }
    setPassword("")
    setFlow({ kind: "password" })
    setMessage(
      reason === "expired"
        ? "Your sign-in request expired or changed. Enter your password again."
        : "Sign-in cancelled. Enter your password to start again.",
    )
  }

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (rateLimited || !username.trim() || !password) return

    setMessage(null)
    try {
      const credentials: LoginCredentials = { username: username.trim(), password }
      const challenge = await beginMfaLogin(credentials)
      setPassword("")
      setFlow(stateForChallenge(challenge))
    } catch (error) {
      const nextLimit = getMfaRateLimitDeadline(error)
      if (nextLimit) setRateLimitDeadline(nextLimit)
      setMessage(getMfaErrorMessage(error, "Unable to start secure sign-in. Try again."))
    }
  }

  function handleChallengeCompleted(result: CompletedLogin | ChallengeState) {
    if (result.status === "authenticated") {
      setPassword("")
      setFlow({ kind: "password" })
      onAuthenticated(result.user)
      return
    }
    setPassword("")
    setFlow(stateForChallenge(result))
  }

  function handleEnrollmentCompleted(result: EnrollmentConfirmationResponse) {
    if (result.status === "authenticated") {
      setFlow({
        kind: "codes",
        codes: result.recovery_codes,
        accountName: result.user.username,
        user: result.user,
      })
      return
    }
    setFlow({ kind: "codes", codes: result.recovery_codes, accountName: username, user: null })
  }

  function handleCodesAcknowledged() {
    if (flow.kind !== "codes") return
    const completedUser = flow.user
    setFlow({ kind: "password" })
    if (completedUser) {
      onAuthenticated(completedUser)
    } else {
      setMessage("Authenticator replaced. Sign in again with the new authenticator.")
    }
  }

  if (flow.kind === "checking") {
    return (
      <Card className="w-full max-w-[440px] p-8">
        <p role="status" className="text-center text-secondary text-fg-muted">
          Checking for an active sign-in…
        </p>
      </Card>
    )
  }

  if (flow.kind === "challenge") {
    return (
      <MfaChallengePanel
        challenge={flow.challenge}
        onCompleted={handleChallengeCompleted}
        onCancel={cancelFlow}
        rateLimitDeadline={rateLimitDeadline}
        onRateLimitDeadlineChange={setRateLimitDeadline}
      />
    )
  }

  if (flow.kind === "enrollment") {
    return (
      <MfaEnrollmentPanel
        challenge={flow.challenge}
        onCompleted={handleEnrollmentCompleted}
        onCancel={cancelFlow}
        rateLimitDeadline={rateLimitDeadline}
        onRateLimitDeadlineChange={setRateLimitDeadline}
      />
    )
  }

  if (flow.kind === "codes") {
    return (
      <RecoveryCodesPanel
        codes={flow.codes}
        accountName={flow.accountName}
        onAcknowledged={handleCodesAcknowledged}
      />
    )
  }

  return (
    <Card className="w-full max-w-[440px] p-6 sm:p-8">
      <div className="mb-7 text-center">
        <div className="mb-3 flex justify-center">
          <img
            src="/adas-logo.png"
            alt="ADAS Logo"
            className="h-auto w-24 object-contain drop-shadow-md"
          />
        </div>
        <h1 className="text-xl font-semibold uppercase tracking-[0.2em] text-fg">ADAS</h1>
        <p className="mt-1 text-caption text-fg-muted">
          Sign in with your password and authenticator
        </p>
      </div>

      {message ? (
        <p
          role="alert"
          className="mb-4 rounded-md border border-danger-border bg-danger-subtle px-4 py-3 text-caption text-danger"
        >
          {message}
        </p>
      ) : null}

      <form onSubmit={handlePasswordSubmit} className="space-y-5">
        <Input
          label="Username"
          type="text"
          autoFocus
          autoComplete="username"
          placeholder="username"
          value={username}
          disabled={rateLimited}
          onChange={(event) => {
            if (!rateLimited) setMessage(null)
            setUsername(event.target.value)
          }}
        />
        <PasswordInput
          label="Password"
          value={password}
          autoComplete="current-password"
          placeholder="password"
          disabled={rateLimited}
          onChange={(value) => {
            if (!rateLimited) setMessage(null)
            setPassword(value)
          }}
        />
        {rateLimited ? (
          <p role="status" className="text-caption text-warning" aria-live="polite">
            Wait {secondsLeft}s before trying another password.
          </p>
        ) : null}
        <Button
          type="submit"
          className="w-full"
          disabled={rateLimited || !username.trim() || !password}
        >
          {rateLimited ? `Try again in ${secondsLeft}s` : "Continue"}
        </Button>
      </form>
    </Card>
  )
}
