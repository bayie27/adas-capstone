import { describe, expect, it } from "vitest"

import { expectedRestoreConfirmation } from "./maintenance"

describe("expectedRestoreConfirmation", () => {
  it("mirrors the backend's RestoreRequestIn.expected_confirmation exactly", () => {
    expect(expectedRestoreConfirmation("abc123")).toBe("RESTORE abc123")
  })
})
