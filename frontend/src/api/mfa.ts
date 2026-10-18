import axios from "axios"

import { API_BASE_URL } from "@/utils/env"
import type { CurrentUserResponse, LoginCredentials } from "@/api/auth"
import api from "@/api/client"

export type ChallengePurpose =
  "login" | "enroll" | "recovery_verify" | "recovery_enroll" | "replace"

export interface ChallengeState {
  status: "mfa_required" | "enrollment_required"
  purpose: ChallengePurpose
  expires_at: string
}

export interface EnrollmentStartResponse {
  provisioning_uri: string
  manual_key: string
  issuer: "ADAS"
  account_name: string
  expires_at: string
}

export interface CompletedLogin {
  status: "authenticated"
  user: CurrentUserResponse
}

export interface CompletedEnrollment extends CompletedLogin {
  recovery_codes: string[]
}

export interface CompletedReplacement {
  status: "reauthentication_required"
  recovery_codes: string[]
}

export type EnrollmentConfirmationResponse = CompletedEnrollment | CompletedReplacement
export type ChallengeVerificationResponse = CompletedLogin | ChallengeState

export interface MfaStatusResponse {
  state: "unenrolled" | "enrolled" | "recovery_pending"
  recovery_codes_remaining: number
  enrolled_at: string | null
  auth_method: "password" | "totp" | "demo_impersonation"
}

export interface RecoveryCodesResponse {
  recovery_codes: string[]
}

/**
 * The staged login/challenge endpoints use their own cookie-enabled client.
 * Proof failures are expected 401 responses here, not a reason to invoke the
 * app-wide session-loss interceptor.
 */
export const mfaAuthClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
})

export async function beginMfaLogin(credentials: LoginCredentials): Promise<ChallengeState> {
  const formData = new URLSearchParams()
  formData.set("username", credentials.username.trim())
  formData.set("password", credentials.password)

  const { data } = await mfaAuthClient.post<ChallengeState>("/auth/login", formData, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  })

  return data
}

export async function getMfaChallenge(): Promise<ChallengeState> {
  const { data } = await mfaAuthClient.get<ChallengeState>("/auth/mfa/challenge")
  return data
}

export async function cancelMfaChallenge(): Promise<void> {
  await mfaAuthClient.delete("/auth/mfa/challenge")
}

export async function getMfaEnrollment(): Promise<EnrollmentStartResponse> {
  const { data } = await mfaAuthClient.post<EnrollmentStartResponse>(
    "/auth/mfa/enrollment/start",
    {},
  )
  return data
}

export async function confirmMfaEnrollment(code: string): Promise<EnrollmentConfirmationResponse> {
  const { data } = await mfaAuthClient.post<EnrollmentConfirmationResponse>(
    "/auth/mfa/enrollment/confirm",
    { code },
  )
  return data
}

export async function verifyMfaChallenge(
  method: "totp" | "recovery",
  code: string,
): Promise<ChallengeVerificationResponse> {
  const { data } = await mfaAuthClient.post<ChallengeVerificationResponse>("/auth/mfa/verify", {
    method,
    code,
  })
  return data
}

/** Authenticated management calls retain the app's real session-loss behavior. */
export async function getMfaStatus(): Promise<MfaStatusResponse> {
  const { data } = await api.get<MfaStatusResponse>("/auth/mfa/status")
  return data
}

export async function rotateMfaRecoveryCodes(
  password: string,
  code: string,
): Promise<RecoveryCodesResponse> {
  const { data } = await api.post<RecoveryCodesResponse>("/auth/mfa/recovery-codes/rotate", {
    password,
    code,
  })
  return data
}

export async function beginMfaReplacement(password: string, code: string): Promise<ChallengeState> {
  const { data } = await api.post<ChallengeState>("/auth/mfa/replacement/start", {
    password,
    code,
  })
  return data
}

export async function beginMfaEnrollmentFromSession(password: string): Promise<ChallengeState> {
  const { data } = await api.post<ChallengeState>("/auth/mfa/enrollment/from-session", {
    password,
  })
  return data
}
