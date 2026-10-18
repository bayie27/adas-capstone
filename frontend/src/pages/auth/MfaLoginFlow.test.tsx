import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MfaLoginFlow } from "./MfaLoginFlow"
import type { ChallengeState, EnrollmentStartResponse } from "@/api/mfa"

vi.mock("qrcode.react", () => ({
  QRCodeSVG: ({ value }: { value: string }) => <svg data-testid="qr-code" data-value={value} />,
}))

vi.mock("@/api/mfa", async () => {
  const actual = await vi.importActual<typeof import("@/api/mfa")>("@/api/mfa")
  return {
    ...actual,
    beginMfaLogin: vi.fn(),
    cancelMfaChallenge: vi.fn(),
    confirmMfaEnrollment: vi.fn(),
    getMfaChallenge: vi.fn(),
    getMfaEnrollment: vi.fn(),
    verifyMfaChallenge: vi.fn(),
  }
})

import {
  beginMfaLogin,
  cancelMfaChallenge,
  confirmMfaEnrollment,
  getMfaChallenge,
  getMfaEnrollment,
  verifyMfaChallenge,
} from "@/api/mfa"

const loginChallenge: ChallengeState = {
  status: "mfa_required",
  purpose: "login",
  expires_at: "2030-01-01T00:05:00Z",
}

const enrollChallenge: ChallengeState = {
  status: "enrollment_required",
  purpose: "enroll",
  expires_at: "2030-01-01T00:15:00Z",
}

const provisioning: EnrollmentStartResponse = {
  provisioning_uri: "otpauth://totp/ADAS:operator?secret=JBSWY3DPEHPK3PXP&issuer=ADAS",
  manual_key: "JBSWY3DPEHPK3PXP",
  issuer: "ADAS",
  account_name: "operator",
  expires_at: enrollChallenge.expires_at,
}

function apiError(code: string, status = 401, retryAfter?: string) {
  return Object.assign(new Error("Request failed"), {
    isAxiosError: true,
    response: {
      status,
      data: { code, detail: "Server detail must stay private." },
      headers: retryAfter === undefined ? {} : { "retry-after": retryAfter },
    },
  })
}

describe("MfaLoginFlow", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    window.sessionStorage.clear()
    vi.mocked(getMfaChallenge).mockRejectedValue(apiError("MFA_CHALLENGE_INVALID"))
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("resumes a challenge on refresh and authenticates only after final MFA", async () => {
    const user = userEvent.setup()
    vi.mocked(getMfaChallenge).mockResolvedValue(loginChallenge)
    vi.mocked(verifyMfaChallenge).mockResolvedValue({
      status: "authenticated",
      user: {
        user_id: 4,
        username: "operator",
        first_name: "Operator",
        last_name: "One",
        role: "Operator",
        is_active: true,
        created_at: "2026-10-01T00:00:00Z",
        updated_at: "2026-10-01T00:00:00Z",
        password_changed_at: null,
        last_login: "2026-10-18T00:00:00Z",
      },
    })
    const onAuthenticated = vi.fn()

    render(<MfaLoginFlow onAuthenticated={onAuthenticated} />)
    expect(await screen.findByLabelText("Authenticator code")).toBeInTheDocument()
    expect(beginMfaLogin).not.toHaveBeenCalled()
    expect(onAuthenticated).not.toHaveBeenCalled()

    await user.type(screen.getByLabelText("Authenticator code"), "000042")
    await user.click(screen.getByRole("button", { name: /verify code/i }))

    expect(verifyMfaChallenge).toHaveBeenCalledWith("totp", "000042")
    expect(onAuthenticated).toHaveBeenCalledWith(expect.objectContaining({ username: "operator" }))
  })

  it("gates completed enrollment navigation on one-time-code acknowledgment", async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const localStorageWrite = vi.spyOn(window.localStorage, "setItem")
    const sessionStorageWrite = vi.spyOn(window.sessionStorage, "setItem")
    const consoleWrites = [
      vi.spyOn(console, "log"),
      vi.spyOn(console, "warn"),
      vi.spyOn(console, "error"),
    ]
    vi.mocked(beginMfaLogin).mockResolvedValue(enrollChallenge)
    vi.mocked(getMfaEnrollment).mockResolvedValue(provisioning)
    const completed = {
      status: "authenticated" as const,
      user: {
        user_id: 4,
        username: "operator",
        first_name: "Operator",
        last_name: "One",
        role: "Operator" as const,
        is_active: true,
        created_at: "2026-10-01T00:00:00Z",
        updated_at: "2026-10-01T00:00:00Z",
        password_changed_at: null,
        last_login: "2026-10-18T00:00:00Z",
      },
      recovery_codes: ["ABCD-EFGH-JKLM"],
    }
    vi.mocked(confirmMfaEnrollment).mockResolvedValue(completed)
    const onAuthenticated = vi.fn()

    render(
      <QueryClientProvider client={queryClient}>
        <MfaLoginFlow onAuthenticated={onAuthenticated} />
      </QueryClientProvider>,
    )
    await screen.findByLabelText("Username")
    await user.type(screen.getByLabelText("Username"), "operator")
    await user.type(screen.getByLabelText("Password"), "disposable-password")
    await user.click(screen.getByRole("button", { name: /continue/i }))

    await screen.findByTestId("qr-code")
    expect(screen.getByLabelText("Authenticator code")).toBeInTheDocument()
    await user.type(screen.getByLabelText("Authenticator code"), "000042")
    await user.click(screen.getByRole("button", { name: /confirm authenticator/i }))

    expect(await screen.findByText("ABCD-EFGH-JKLM")).toBeInTheDocument()
    expect(onAuthenticated).not.toHaveBeenCalled()
    await user.click(screen.getByRole("checkbox", { name: /i saved these codes/i }))
    await user.click(screen.getByRole("button", { name: /continue/i }))

    expect(onAuthenticated).toHaveBeenCalledOnce()
    expect(onAuthenticated).toHaveBeenCalledWith(completed.user)
    expect(screen.queryByText("ABCD-EFGH-JKLM")).not.toBeInTheDocument()
    expect(localStorageWrite).not.toHaveBeenCalled()
    expect(sessionStorageWrite).not.toHaveBeenCalled()
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)
    expect(window.location.search).toBe("")
    expect(consoleWrites.flatMap((spy) => spy.mock.calls.flat()).join(" ")).not.toContain(
      "disposable-password",
    )
    expect(consoleWrites.flatMap((spy) => spy.mock.calls.flat()).join(" ")).not.toContain(
      "ABCD-EFGH-JKLM",
    )
  })

  it("keeps the server Retry-After limit across method changes and flow restart", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
    vi.mocked(beginMfaLogin).mockResolvedValue(loginChallenge)
    vi.mocked(verifyMfaChallenge).mockRejectedValue(apiError("AUTH_RATE_LIMITED", 429, "45"))

    render(<MfaLoginFlow onAuthenticated={vi.fn()} />)
    await screen.findByLabelText("Username")
    await user.type(screen.getByLabelText("Username"), "operator")
    await user.type(screen.getByLabelText("Password"), "password")
    await user.click(screen.getByRole("button", { name: /continue/i }))
    await screen.findByLabelText("Authenticator code")
    await user.type(screen.getByLabelText("Authenticator code"), "123456")
    await user.click(screen.getByRole("button", { name: /verify code/i }))
    expect(await screen.findByRole("button", { name: /try again in \d+s/i })).toBeDisabled()

    await user.click(screen.getByRole("button", { name: /use a recovery code/i }))
    await user.type(screen.getByLabelText("Recovery code"), "ABCD-EFGH-JKLM")
    expect(screen.getByRole("button", { name: /try again in \d+s/i })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: /cancel and start over/i }))
    await screen.findByLabelText("Password")

    expect(screen.getByRole("button", { name: /try again in \d+s/i })).toBeDisabled()
    expect(screen.getByLabelText("Password")).toHaveValue("")
    expect(cancelMfaChallenge).toHaveBeenCalledOnce()
  })

  it("turns recovery verification into fresh enrollment and requires code acknowledgment", async () => {
    const user = userEvent.setup()
    const recoveryChallenge: ChallengeState = {
      status: "mfa_required",
      purpose: "recovery_verify",
      expires_at: "2030-01-01T00:05:00Z",
    }
    const recoveryEnrollment: ChallengeState = {
      status: "enrollment_required",
      purpose: "recovery_enroll",
      expires_at: "2030-01-01T00:15:00Z",
    }
    const completedReplacement = {
      status: "reauthentication_required" as const,
      recovery_codes: ["WXYZ-1234-ABCD"],
    }
    const onAuthenticated = vi.fn()
    vi.mocked(getMfaChallenge).mockResolvedValue(recoveryChallenge)
    vi.mocked(verifyMfaChallenge).mockResolvedValue(recoveryEnrollment)
    vi.mocked(getMfaEnrollment).mockResolvedValue(provisioning)
    vi.mocked(confirmMfaEnrollment).mockResolvedValue(completedReplacement)

    render(<MfaLoginFlow onAuthenticated={onAuthenticated} />)
    await user.type(await screen.findByLabelText("Recovery code"), "ABCD-EFGH-JKLM")
    await user.click(screen.getByRole("button", { name: /verify code/i }))

    expect(verifyMfaChallenge).toHaveBeenCalledWith("recovery", "ABCD-EFGH-JKLM")
    expect(await screen.findByTestId("qr-code")).toBeInTheDocument()
    expect(getMfaEnrollment).toHaveBeenCalledOnce()
    await user.type(screen.getByLabelText("Authenticator code"), "000042")
    await user.click(screen.getByRole("button", { name: /confirm authenticator/i }))

    expect(await screen.findByText("WXYZ-1234-ABCD")).toBeInTheDocument()
    expect(onAuthenticated).not.toHaveBeenCalled()
    await user.click(screen.getByRole("checkbox", { name: /i saved these codes/i }))
    await user.click(screen.getByRole("button", { name: /continue/i }))

    expect(await screen.findByLabelText("Password")).toBeInTheDocument()
    expect(screen.getByRole("alert")).toHaveTextContent(/sign in again with the new authenticator/i)
    expect(onAuthenticated).not.toHaveBeenCalled()
  })

  it("does not redisplay a committed code batch after reload or a lost response", async () => {
    const user = userEvent.setup()
    const completed = {
      status: "authenticated" as const,
      user: {
        user_id: 4,
        username: "operator",
        first_name: "Operator",
        last_name: "One",
        role: "Operator" as const,
        is_active: true,
        created_at: "2026-10-01T00:00:00Z",
        updated_at: "2026-10-01T00:00:00Z",
        password_changed_at: null,
        last_login: "2026-10-18T00:00:00Z",
      },
      recovery_codes: ["ABCD-EFGH-JKLM"],
    }
    vi.mocked(getMfaChallenge).mockResolvedValue(enrollChallenge)
    vi.mocked(getMfaEnrollment).mockResolvedValue(provisioning)
    vi.mocked(confirmMfaEnrollment).mockResolvedValue(completed)
    const firstLoad = render(<MfaLoginFlow onAuthenticated={vi.fn()} />)
    await screen.findByTestId("qr-code")
    await user.type(screen.getByLabelText("Authenticator code"), "000042")
    await user.click(screen.getByRole("button", { name: /confirm authenticator/i }))
    expect(await screen.findByText("ABCD-EFGH-JKLM")).toBeInTheDocument()
    firstLoad.unmount()

    vi.mocked(getMfaChallenge).mockRejectedValue(apiError("MFA_CHALLENGE_INVALID"))
    render(<MfaLoginFlow onAuthenticated={vi.fn()} />)

    expect(await screen.findByLabelText("Password")).toBeInTheDocument()
    expect(screen.queryByText("ABCD-EFGH-JKLM")).not.toBeInTheDocument()
    expect(getMfaEnrollment).toHaveBeenCalledOnce()
    expect(window.localStorage.getItem("adas-auth-session")).toBeNull()
  })

  it("restarts a superseded challenge without treating it as a completed login", async () => {
    const user = userEvent.setup()
    vi.mocked(getMfaChallenge).mockResolvedValue(loginChallenge)
    vi.mocked(verifyMfaChallenge).mockRejectedValue(apiError("MFA_CHALLENGE_INVALID"))
    const onAuthenticated = vi.fn()

    render(<MfaLoginFlow onAuthenticated={onAuthenticated} />)
    await screen.findByLabelText("Authenticator code")
    await user.type(screen.getByLabelText("Authenticator code"), "123456")
    await user.click(screen.getByRole("button", { name: /verify code/i }))

    await waitFor(() => expect(screen.getByLabelText("Password")).toBeInTheDocument())
    expect(screen.getByRole("alert")).toHaveTextContent(/sign-in request expired/i)
    expect(onAuthenticated).not.toHaveBeenCalled()
  })
})
