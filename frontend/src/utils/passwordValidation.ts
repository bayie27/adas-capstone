/**
 * Mirrors the backend's password rules (`validate_password_strength` +
 * `Field(min_length=8, max_length=128)` in backend/app/schemas/user.py) so an
 * obviously-invalid new password never costs a round trip. Only a *new*
 * password is checked against strength rules — a current/old password is
 * validated by the server alone, since its job there is proving identity,
 * not meeting today's strength policy.
 */
export function validateNewPassword(value: string): string | undefined {
  if (!value) return "Password is required."
  if (value.length < 8) return "Password must be at least 8 characters long."
  if (value.length > 128) return "Password must be 128 characters or fewer."
  if (!/\d/.test(value)) return "Password must contain at least 1 number."
  return undefined
}

export function validatePasswordConfirmation(
  password: string,
  confirmation: string,
): string | undefined {
  if (!confirmation) return "Please confirm the password."
  if (password !== confirmation) return "Passwords do not match."
  return undefined
}

export function validateRequiredPassword(value: string, label: string): string | undefined {
  return value ? undefined : `${label} is required.`
}
