import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MfaSettingsCard } from "./MfaSettingsCard"
import { MfaSensitiveFlowProvider } from "@/components/auth/MfaSensitiveFlowProvider"
import type { ChallengeState, EnrollmentStartResponse, MfaStatusResponse } from "@/api/mfa"
import { isAuthRedirectSuspended } from "@/api/client"

vi.mock("qrcode.react", () => ({
  QRCodeSVG: ({ value }: { value: string }) => <svg data-testid="qr-code" data-value={value} />,
}))

vi.mock("@/api/mfa", async () => {
  const actual = await vi.importActual<typeof import("@/api/mfa")>("@/api/mfa")
  return {
    ...actual,
    beginMfaEnrollmentFromSession: vi.fn(),
    beginMfaReplacement: vi.fn(),
    cancelMfaChallenge: vi.fn(),
    confirmMfaEnrollment: vi.fn(),
    getMfaEnrollment: vi.fn(),
    getMfaStatus: vi.fn(),
    rotateMfaRecoveryCodes: vi.fn(),
  }
})

import {
  beginMfaEnrollmentFromSession,
  beginMfaReplacement,
  cancelMfaChallenge,
  confirmMfaEnrollment,
  getMfaEnrollment,
  getMfaStatus,
  rotateMfaRecoveryCodes,
} from "@/api/mfa"

const enrolledStatus: MfaStatusResponse = {
  state: "enrolled",
  recovery_codes_remaining: 8,
  enrolled_at: "2026-10-01T10:00:00Z",
  auth_method: "totp",
}

const replaceChallenge: ChallengeState = {
  status: "enrollment_required",
  purpose: "replace",
  expires_at: "2030-01-01T00:15:00Z",
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
  expires_at: replaceChallenge.expires_at,
}

function apiError(code: string) {
  return Object.assign(new Error("Request failed"), {
    isAxiosError: true,
    response: {
      status: 401,
      data: { code, detail: "Private backend proof detail." },
      headers: {},
    },
  })
}

function renderCard(
  status: MfaStatusResponse = enrolledStatus,
  onSessionRevoked = vi.fn(),
  onSignedOut = vi.fn(),
) {
  vi.mocked(getMfaStatus).mockResolvedValue(status)
  return {
    onSessionRevoked,
    onSignedOut,
    ...render(
      <MfaSensitiveFlowProvider>
        <MfaSettingsCard onSessionRevoked={onSessionRevoked} onSignedOut={onSignedOut} />
      </MfaSensitiveFlowProvider>,
    ),
  }
}

async function startReplacement(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByText(/8 recovery codes remaining/i)
  await user.click(screen.getByRole("button", { name: /replace authenticator/i }))
  await user.type(screen.getByLabelText("Current password"), "correct-password")
  await user.type(screen.getByLabelText("Current authenticator code"), "000123")
  await user.click(screen.getByRole("button", { name: /start replacement/i }))
  await screen.findByTestId("qr-code")
}

describe("MfaSettingsCard", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getMfaStatus).mockResolvedValue(enrolledStatus)
    vi.mocked(getMfaEnrollment).mockResolvedValue(provisioning)
  })
  afterEach(() => {
    vi.restoreAllMocks()
    expect(isAuthRedirectSuspended()).toBe(false)
  })

  it("shows safe status and cancels replacement without signing out or replacing the old factor", async () => {
    const user = userEvent.setup()
    const onSessionRevoked = vi.fn()
    const onSignedOut = vi.fn()
    vi.mocked(beginMfaReplacement).mockResolvedValue(replaceChallenge)
    renderCard(enrolledStatus, onSessionRevoked, onSignedOut)

    expect(await screen.findByText(/8 recovery codes remaining/i)).toBeInTheDocument()
    expect(screen.getByText(/enabled since october 1, 2026/i)).toBeInTheDocument()
    expect(screen.queryByText(/JBSWY3DPEHPK3PXP/)).not.toBeInTheDocument()
    await startReplacement(user)
    expect(beginMfaReplacement).toHaveBeenCalledWith("correct-password", "000123")
    await user.click(screen.getByRole("button", { name: /cancel setup/i }))

    expect(cancelMfaChallenge).toHaveBeenCalledOnce()
    expect(onSessionRevoked).not.toHaveBeenCalled()
    expect(onSignedOut).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: /replace authenticator/i })).toBeInTheDocument()
  })

  it("registers replacement codes before revoking the session and signs out only after acknowledgment", async () => {
    const user = userEvent.setup()
    const order: string[] = []
    const onSessionRevoked = vi.fn(() => order.push("session-revoked"))
    const onSignedOut = vi.fn(() => order.push("signed-out"))
    vi.mocked(beginMfaReplacement).mockResolvedValue(replaceChallenge)
    vi.mocked(confirmMfaEnrollment).mockResolvedValue({
      status: "reauthentication_required",
      recovery_codes: ["ABCD-EFGH-JKLM"],
    })
    renderCard(enrolledStatus, onSessionRevoked, onSignedOut)

    await startReplacement(user)
    await user.type(screen.getByLabelText("Authenticator code"), "654321")
    await user.click(screen.getByRole("button", { name: /confirm authenticator/i }))

    expect(confirmMfaEnrollment).toHaveBeenCalledWith("654321")
    expect(await screen.findByText("ABCD-EFGH-JKLM")).toBeInTheDocument()
    expect(order).toEqual(["session-revoked"])
    expect(onSignedOut).not.toHaveBeenCalled()
    expect(isAuthRedirectSuspended()).toBe(true)
    await user.click(screen.getByRole("checkbox", { name: /i saved these codes/i }))
    await user.click(screen.getByRole("button", { name: /continue/i }))

    expect(order).toEqual(["session-revoked", "signed-out"])
    expect(isAuthRedirectSuspended()).toBe(false)
  })

  it("keeps proof failures inline and does not revoke a valid session", async () => {
    const user = userEvent.setup()
    const onSessionRevoked = vi.fn()
    const onSignedOut = vi.fn()
    vi.mocked(beginMfaReplacement).mockRejectedValue(apiError("MFA_INVALID_CODE"))
    renderCard(enrolledStatus, onSessionRevoked, onSignedOut)

    await screen.findByText(/8 recovery codes remaining/i)
    await user.click(screen.getByRole("button", { name: /replace authenticator/i }))
    await user.type(screen.getByLabelText("Current password"), "correct-password")
    await user.type(screen.getByLabelText("Current authenticator code"), "111111")
    await user.click(screen.getByRole("button", { name: /start replacement/i }))

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn.t verify your credentials/i)
    expect(screen.getByRole("alert")).not.toHaveTextContent("Private backend proof detail")
    expect(onSessionRevoked).not.toHaveBeenCalled()
    expect(onSignedOut).not.toHaveBeenCalled()
  })

  it("rotates recovery codes in place without clearing the Profile session", async () => {
    const user = userEvent.setup()
    const onSessionRevoked = vi.fn()
    const onSignedOut = vi.fn()
    vi.mocked(rotateMfaRecoveryCodes).mockResolvedValue({
      recovery_codes: [
        "WXYZ-ABCD-EFGH",
        "IJKL-MNOP-QRST",
        "UVWX-YZAB-CDEF",
        "GHIJ-KLMN-OPQR",
        "STUV-WXYZ-ABCD",
        "EFGH-IJKL-MNOP",
        "QRST-UVWX-YZAB",
        "CDEF-GHIJ-KLMN",
        "OPQR-STUV-WXYZ",
        "ABCD-EFGH-IJKL",
      ],
    })
    renderCard(enrolledStatus, onSessionRevoked, onSignedOut)

    await screen.findByText(/8 recovery codes remaining/i)
    await user.click(screen.getByRole("button", { name: /rotate recovery codes/i }))
    await user.type(screen.getByLabelText("Password"), "correct-password")
    await user.type(screen.getByLabelText("Current authenticator code"), "000123")
    await user.click(screen.getByRole("button", { name: /rotate codes/i }))
    expect(await screen.findByText("WXYZ-ABCD-EFGH")).toBeInTheDocument()

    await user.click(screen.getByRole("checkbox", { name: /i saved these codes/i }))
    await user.click(screen.getByRole("button", { name: /continue/i }))

    expect(onSessionRevoked).not.toHaveBeenCalled()
    expect(onSignedOut).not.toHaveBeenCalled()
    expect(screen.getByText(/10 recovery codes remaining/i)).toBeInTheDocument()
  })

  it("requires a fresh password before unenrolled demo enrollment and closes the impersonation after codes", async () => {
    const user = userEvent.setup()
    const demoStatus: MfaStatusResponse = {
      state: "unenrolled",
      recovery_codes_remaining: 0,
      enrolled_at: null,
      auth_method: "demo_impersonation",
    }
    const onSessionRevoked = vi.fn()
    const onSignedOut = vi.fn()
    vi.mocked(beginMfaEnrollmentFromSession).mockResolvedValue(enrollChallenge)
    vi.mocked(confirmMfaEnrollment).mockResolvedValue({
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
      recovery_codes: ["ABCD-EFGH-JKLM"],
    })
    renderCard(demoStatus, onSessionRevoked, onSignedOut)

    await user.click(await screen.findByRole("button", { name: /set up authenticator/i }))
    expect(screen.getByRole("button", { name: /continue setup/i })).toBeDisabled()
    await user.type(screen.getByLabelText("Password"), "fresh-password")
    await user.click(screen.getByRole("button", { name: /continue setup/i }))
    expect(beginMfaEnrollmentFromSession).toHaveBeenCalledWith("fresh-password")
    await screen.findByTestId("qr-code")
    await user.type(screen.getByLabelText("Authenticator code"), "000123")
    await user.click(screen.getByRole("button", { name: /confirm authenticator/i }))
    await screen.findByText("ABCD-EFGH-JKLM")

    expect(onSessionRevoked).toHaveBeenCalledOnce()
    expect(onSignedOut).not.toHaveBeenCalled()
    await user.click(screen.getByRole("checkbox", { name: /i saved these codes/i }))
    await user.click(screen.getByRole("button", { name: /continue/i }))
    expect(onSignedOut).toHaveBeenCalledOnce()
  })

  it("requires password and current-factor proof for an enrolled demo session", async () => {
    const user = userEvent.setup()
    const demoEnrolled: MfaStatusResponse = {
      ...enrolledStatus,
      auth_method: "demo_impersonation",
    }
    vi.mocked(beginMfaReplacement).mockResolvedValue(replaceChallenge)
    renderCard(demoEnrolled)

    expect(
      await screen.findByText(
        /demo session still requires your password and current authenticator code/i,
      ),
    ).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /replace authenticator/i }))
    expect(screen.getByRole("button", { name: /start replacement/i })).toBeDisabled()
    await user.type(screen.getByLabelText("Current password"), "fresh-password")
    await user.type(screen.getByLabelText("Current authenticator code"), "000654")
    await user.click(screen.getByRole("button", { name: /start replacement/i }))

    expect(beginMfaReplacement).toHaveBeenCalledWith("fresh-password", "000654")
  })

  it("routes recovery-pending accounts through recovery login without a setup shortcut", async () => {
    const recoveryPending: MfaStatusResponse = {
      state: "recovery_pending",
      recovery_codes_remaining: 0,
      enrolled_at: null,
      auth_method: "password",
    }
    renderCard(recoveryPending)

    expect(
      await screen.findByText(/sign in with your password and another unused recovery code/i),
    ).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /set up authenticator/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /replace authenticator/i })).not.toBeInTheDocument()
  })
})
