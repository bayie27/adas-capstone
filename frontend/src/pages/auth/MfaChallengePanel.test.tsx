import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MfaChallengePanel } from "./MfaChallengePanel"
import type { ChallengeState } from "@/api/mfa"

vi.mock("@/api/mfa", async () => {
  const actual = await vi.importActual<typeof import("@/api/mfa")>("@/api/mfa")
  return { ...actual, verifyMfaChallenge: vi.fn() }
})

import { verifyMfaChallenge } from "@/api/mfa"

const challenge: ChallengeState = {
  status: "mfa_required",
  purpose: "login",
  expires_at: "2030-01-01T00:05:00Z",
}

function makeError(code: string, status = 401, retryAfter?: string) {
  return Object.assign(new Error("Request failed"), {
    isAxiosError: true,
    response: {
      status,
      data: { code, detail: "Do not display server proof details." },
      headers: retryAfter === undefined ? {} : { "retry-after": retryAfter },
    },
  })
}

describe("MfaChallengePanel", () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => vi.useRealTimers())

  it("submits pasted leading-zero TOTP input and returns the final discriminated result", async () => {
    const user = userEvent.setup()
    const completed = { status: "authenticated" as const, user: { user_id: 5 } }
    vi.mocked(verifyMfaChallenge).mockResolvedValue(completed as never)
    const onCompleted = vi.fn()

    render(<MfaChallengePanel challenge={challenge} onCompleted={onCompleted} onCancel={vi.fn()} />)
    const codeInput = screen.getByLabelText("Authenticator code")
    expect(codeInput).toHaveFocus()
    await user.click(codeInput)
    await user.paste("001234")
    await user.click(screen.getByRole("button", { name: /verify/i }))

    expect(verifyMfaChallenge).toHaveBeenCalledWith("totp", "001234")
    expect(onCompleted).toHaveBeenCalledWith(completed)
  })

  it("keeps invalid proofs inline without completing or exposing server detail", async () => {
    const user = userEvent.setup()
    const onCompleted = vi.fn()
    vi.mocked(verifyMfaChallenge).mockRejectedValue(makeError("MFA_INVALID_CODE"))

    render(<MfaChallengePanel challenge={challenge} onCompleted={onCompleted} onCancel={vi.fn()} />)
    await user.type(screen.getByLabelText("Authenticator code"), "123456")
    await user.click(screen.getByRole("button", { name: /verify/i }))

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn.t verify your credentials/i)
    expect(screen.getByRole("alert")).not.toHaveTextContent("Do not display server proof details")
    expect(onCompleted).not.toHaveBeenCalled()
  })

  it("keeps Retry-After active while switching proof methods", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
    vi.mocked(verifyMfaChallenge).mockRejectedValue(makeError("AUTH_RATE_LIMITED", 429, "40"))

    render(<MfaChallengePanel challenge={challenge} onCompleted={vi.fn()} onCancel={vi.fn()} />)
    await user.type(screen.getByLabelText("Authenticator code"), "123456")
    await user.click(screen.getByRole("button", { name: /verify/i }))
    expect(await screen.findByRole("button", { name: /try again in \d+s/i })).toBeDisabled()

    await user.click(screen.getByRole("button", { name: /use a recovery code/i }))
    expect(screen.getByLabelText("Recovery code")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /try again in \d+s/i })).toBeDisabled()
  })

  it.each([undefined, "not-a-number"])(
    "uses the existing 60-second fallback when Retry-After is %s",
    async (retryAfter) => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
      vi.mocked(verifyMfaChallenge).mockRejectedValue(
        makeError("AUTH_RATE_LIMITED", 429, retryAfter),
      )

      render(<MfaChallengePanel challenge={challenge} onCompleted={vi.fn()} onCancel={vi.fn()} />)
      await user.type(screen.getByLabelText("Authenticator code"), "123456")
      await user.click(screen.getByRole("button", { name: /verify code/i }))

      expect(await screen.findByRole("button", { name: /try again in (5\d|60)s/i })).toBeDisabled()
    },
  )

  it("returns an expired challenge to the caller exactly once", async () => {
    vi.useFakeTimers()
    const onCancel = vi.fn()
    const expiring = { ...challenge, expires_at: new Date(Date.now() + 1_000).toISOString() }

    render(<MfaChallengePanel challenge={expiring} onCompleted={vi.fn()} onCancel={onCancel} />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000)
    })

    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
