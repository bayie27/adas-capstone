import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { MfaEnrollmentPanel } from "./MfaEnrollmentPanel"
import type {
  ChallengeState,
  EnrollmentConfirmationResponse,
  EnrollmentStartResponse,
} from "@/api/mfa"

vi.mock("qrcode.react", () => ({
  QRCodeSVG: ({ value }: { value: string }) => <svg data-testid="qr-code" data-value={value} />,
}))

vi.mock("@/api/mfa", async () => {
  const actual = await vi.importActual<typeof import("@/api/mfa")>("@/api/mfa")
  return {
    ...actual,
    getMfaEnrollment: vi.fn(),
    confirmMfaEnrollment: vi.fn(),
  }
})

import { confirmMfaEnrollment, getMfaEnrollment } from "@/api/mfa"

const challenge: ChallengeState = {
  status: "enrollment_required",
  purpose: "enroll",
  expires_at: "2030-01-01T00:15:00Z",
}

const provisioning: EnrollmentStartResponse = {
  provisioning_uri:
    "otpauth://totp/ADAS:operator?secret=JBSWY3DPEHPK3PXP&issuer=ADAS&digits=6&period=30",
  manual_key: "JBSWY3DPEHPK3PXP",
  issuer: "ADAS",
  account_name: "operator",
  expires_at: challenge.expires_at,
}

function makeProofError() {
  return Object.assign(new Error("Request failed"), {
    isAxiosError: true,
    response: {
      status: 401,
      data: { code: "MFA_INVALID_CODE", detail: "Private proof detail" },
      headers: {},
    },
  })
}

describe("MfaEnrollmentPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getMfaEnrollment).mockResolvedValue(provisioning)
  })

  it("renders a local QR value that uses the same secret as the manual key", async () => {
    const { container } = render(
      <MfaEnrollmentPanel challenge={challenge} onCompleted={vi.fn()} onCancel={vi.fn()} />,
    )

    const qr = await screen.findByTestId("qr-code")
    const qrUri = new URL(qr.getAttribute("data-value")!)

    expect(qr.tagName.toLowerCase()).toBe("svg")
    expect(container.querySelector("img")).toBeNull()
    expect(qrUri.protocol).toBe("otpauth:")
    expect(qrUri.searchParams.get("secret")).toBe(provisioning.manual_key)
    expect(screen.getByText(provisioning.manual_key)).toBeInTheDocument()
    expect(screen.getByText(/use a local authenticator app/i)).toBeInTheDocument()
    expect(screen.getByText(/turn off cloud sync/i)).toBeInTheDocument()
    expect(screen.getByText(/if you just used a code, wait for the next one/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Authenticator code")).toHaveFocus()
    expect(getMfaEnrollment).toHaveBeenCalledOnce()
  })

  it("keeps the provisioning screen open after a wrong confirmation code", async () => {
    const user = userEvent.setup()
    vi.mocked(confirmMfaEnrollment).mockRejectedValue(makeProofError())
    const onCompleted = vi.fn()

    render(
      <MfaEnrollmentPanel challenge={challenge} onCompleted={onCompleted} onCancel={vi.fn()} />,
    )
    await screen.findByTestId("qr-code")
    await user.type(screen.getByLabelText("Authenticator code"), "000123")
    await user.click(screen.getByRole("button", { name: /confirm authenticator/i }))

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn.t verify your credentials/i)
    expect(screen.getByTestId("qr-code")).toBeInTheDocument()
    expect(screen.getByRole("alert")).not.toHaveTextContent("Private proof detail")
    expect(onCompleted).not.toHaveBeenCalled()
    expect(confirmMfaEnrollment).toHaveBeenCalledWith("000123")
  })

  it("ignores duplicate confirmation submits while the replacement request is pending", async () => {
    let resolveConfirmation!: (result: EnrollmentConfirmationResponse) => void
    const pendingConfirmation = new Promise<EnrollmentConfirmationResponse>((resolve) => {
      resolveConfirmation = resolve
    })
    vi.mocked(confirmMfaEnrollment).mockReturnValue(pendingConfirmation)
    const onCompleted = vi.fn()

    render(
      <MfaEnrollmentPanel challenge={challenge} onCompleted={onCompleted} onCancel={vi.fn()} />,
    )
    await screen.findByTestId("qr-code")
    await userEvent.setup().type(screen.getByLabelText("Authenticator code"), "000321")
    const form = screen.getByLabelText("Authenticator code").closest("form")
    expect(form).not.toBeNull()

    fireEvent.submit(form!)
    fireEvent.submit(form!)

    expect(confirmMfaEnrollment).toHaveBeenCalledOnce()
    resolveConfirmation({
      status: "reauthentication_required",
      recovery_codes: ["WXYZ-1234-ABCD"],
    })
    await waitFor(() => expect(onCompleted).toHaveBeenCalledOnce())
  })
})
