import { describe, expect, it } from "vitest"

import { getFieldValidationMessage } from "./apiFieldErrors"

function validationError(errors: unknown[]) {
  return {
    isAxiosError: true,
    response: {
      status: 422,
      data: { code: "VALIDATION_ERROR", detail: "Validation failed", errors },
    },
  }
}

describe("getFieldValidationMessage", () => {
  it("returns the message for a field named at the end of its loc path", () => {
    const error = validationError([
      {
        loc: ["body", "new_password"],
        msg: "Password must contain at least 1 number.",
        type: "value_error",
      },
    ])
    expect(getFieldValidationMessage(error, "new_password")).toBe(
      "Password must contain at least 1 number.",
    )
  })

  it("returns undefined when no issue names the field", () => {
    const error = validationError([
      {
        loc: ["body", "old_password"],
        msg: "String should have at least 8 characters",
        type: "string_too_short",
      },
    ])
    expect(getFieldValidationMessage(error, "new_password")).toBeUndefined()
  })

  it("returns undefined when the response is not a 422", () => {
    const error = {
      isAxiosError: true,
      response: {
        status: 400,
        data: { code: "PRECONDITION_FAILED", detail: "Current password is incorrect." },
      },
    }
    expect(getFieldValidationMessage(error, "old_password")).toBeUndefined()
  })

  it("returns undefined for a non-axios error", () => {
    expect(getFieldValidationMessage(new Error("network down"), "new_password")).toBeUndefined()
  })

  it("returns undefined when errors[] is absent", () => {
    const error = {
      isAxiosError: true,
      response: { status: 422, data: { code: "VALIDATION_ERROR", detail: "Validation failed" } },
    }
    expect(getFieldValidationMessage(error, "new_password")).toBeUndefined()
  })
})
