import { afterEach, describe, expect, it, vi } from "vitest"

import { API_BASE_URL } from "@/utils/env"
import api from "@/api/client"
import {
  beginMfaEnrollmentFromSession,
  beginMfaLogin,
  beginMfaReplacement,
  cancelMfaChallenge,
  confirmMfaEnrollment,
  getMfaChallenge,
  getMfaEnrollment,
  getMfaStatus,
  mfaAuthClient,
  rotateMfaRecoveryCodes,
  verifyMfaChallenge,
} from "./mfa"

const challenge = {
  status: "mfa_required" as const,
  purpose: "login" as const,
  expires_at: "2026-10-18T12:05:00Z",
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe("MFA API adapters", () => {
  it("uses a credentialed auth client and keeps password-stage login discriminated", async () => {
    const post = vi.spyOn(mfaAuthClient, "post").mockResolvedValue({ data: challenge } as never)

    const result = await beginMfaLogin({ username: " operator ", password: "one-time-secret" })

    expect(mfaAuthClient.defaults.baseURL).toBe(API_BASE_URL)
    expect(mfaAuthClient.defaults.withCredentials).toBe(true)
    expect(post).toHaveBeenCalledOnce()
    expect(post.mock.calls[0][0]).toBe("/auth/login")
    const body = post.mock.calls[0][1] as URLSearchParams
    expect(body.get("username")).toBe("operator")
    expect(body.get("password")).toBe("one-time-secret")
    expect(post.mock.calls[0][2]?.headers).toMatchObject({
      "Content-Type": "application/x-www-form-urlencoded",
    })
    expect(result).toEqual(challenge)
    expect("user" in result).toBe(false)
  })

  it("matches challenge, enrollment, confirmation, and proof JSON contracts", async () => {
    const get = vi.spyOn(mfaAuthClient, "get").mockResolvedValue({ data: challenge } as never)
    const remove = vi.spyOn(mfaAuthClient, "delete").mockResolvedValue({} as never)
    const post = vi.spyOn(mfaAuthClient, "post")
    post
      .mockResolvedValueOnce({
        data: {
          provisioning_uri: "otpauth://totp/ADAS:operator?secret=JBSWY3DPEHPK3PXP&issuer=ADAS",
          manual_key: "JBSWY3DPEHPK3PXP",
          issuer: "ADAS",
          account_name: "operator",
          expires_at: challenge.expires_at,
        },
      } as never)
      .mockResolvedValueOnce({
        data: {
          status: "authenticated",
          user: { user_id: 4, username: "operator", role: "Operator" },
          recovery_codes: ["AAAA-BBBB-CCCC"],
        },
      } as never)
      .mockResolvedValueOnce({ data: challenge } as never)

    await expect(getMfaChallenge()).resolves.toEqual(challenge)
    await cancelMfaChallenge()
    await expect(getMfaEnrollment()).resolves.toMatchObject({ issuer: "ADAS" })
    await expect(confirmMfaEnrollment("001234")).resolves.toMatchObject({
      status: "authenticated",
      recovery_codes: ["AAAA-BBBB-CCCC"],
    })
    await expect(verifyMfaChallenge("totp", "001234")).resolves.toEqual(challenge)

    expect(get).toHaveBeenCalledWith("/auth/mfa/challenge")
    expect(remove).toHaveBeenCalledWith("/auth/mfa/challenge")
    expect(post.mock.calls.map(([path]) => path)).toEqual([
      "/auth/mfa/enrollment/start",
      "/auth/mfa/enrollment/confirm",
      "/auth/mfa/verify",
    ])
    expect(post.mock.calls.map(([, body]) => body)).toEqual([
      {},
      { code: "001234" },
      { method: "totp", code: "001234" },
    ])
  })

  it("routes authenticated management through the session-aware client", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({
      data: {
        state: "enrolled",
        recovery_codes_remaining: 8,
        enrolled_at: "2026-10-01T10:00:00Z",
        auth_method: "totp",
      },
    } as never)
    const post = vi.spyOn(api, "post")
    post
      .mockResolvedValueOnce({ data: { recovery_codes: ["AAAA-BBBB-CCCC"] } } as never)
      .mockResolvedValueOnce({ data: { ...challenge, purpose: "replace" } } as never)
      .mockResolvedValueOnce({ data: { ...challenge, purpose: "enroll" } } as never)

    await expect(getMfaStatus()).resolves.toMatchObject({ state: "enrolled" })
    await expect(rotateMfaRecoveryCodes("password", "001234")).resolves.toEqual({
      recovery_codes: ["AAAA-BBBB-CCCC"],
    })
    await expect(beginMfaReplacement("password", "001234")).resolves.toMatchObject({
      purpose: "replace",
    })
    await expect(beginMfaEnrollmentFromSession("password")).resolves.toMatchObject({
      purpose: "enroll",
    })

    expect(api.defaults.withCredentials).toBe(true)
    expect(get).toHaveBeenCalledWith("/auth/mfa/status")
    expect(post.mock.calls).toEqual([
      ["/auth/mfa/recovery-codes/rotate", { password: "password", code: "001234" }],
      ["/auth/mfa/replacement/start", { password: "password", code: "001234" }],
      ["/auth/mfa/enrollment/from-session", { password: "password" }],
    ])
  })
})
