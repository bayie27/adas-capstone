import { describe, expect, it } from "vitest"

import {
  validateNewPassword,
  validatePasswordConfirmation,
  validateRequiredPassword,
} from "./passwordValidation"

describe("validateNewPassword", () => {
  it("requires a value", () => {
    expect(validateNewPassword("")).toBe("Password is required.")
  })

  it("rejects fewer than 8 characters", () => {
    expect(validateNewPassword("abc123")).toBe("Password must be at least 8 characters long.")
  })

  it("rejects more than 128 characters", () => {
    expect(validateNewPassword("a1".repeat(65))).toBe("Password must be 128 characters or fewer.")
  })

  it("rejects a password with no digit", () => {
    expect(validateNewPassword("abcdefgh")).toBe("Password must contain at least 1 number.")
  })

  it("accepts a password meeting every rule", () => {
    expect(validateNewPassword("abcdefg1")).toBeUndefined()
  })

  it("accepts exactly 8 and exactly 128 characters", () => {
    expect(validateNewPassword("abcdefg1")).toBeUndefined()
    expect(validateNewPassword(`${"a".repeat(127)}1`)).toBeUndefined()
  })
})

describe("validatePasswordConfirmation", () => {
  it("requires a confirmation value", () => {
    expect(validatePasswordConfirmation("abcdefg1", "")).toBe("Please confirm the password.")
  })

  it("rejects a mismatch", () => {
    expect(validatePasswordConfirmation("abcdefg1", "abcdefg2")).toBe("Passwords do not match.")
  })

  it("accepts a matching confirmation", () => {
    expect(validatePasswordConfirmation("abcdefg1", "abcdefg1")).toBeUndefined()
  })
})

describe("validateRequiredPassword", () => {
  it("requires a value, using the given label", () => {
    expect(validateRequiredPassword("", "Current password")).toBe("Current password is required.")
  })

  it("accepts any non-empty value", () => {
    expect(validateRequiredPassword("x", "Current password")).toBeUndefined()
  })
})
