import { describe, expect, it } from "vitest"

import { expectedRestoreConfirmation } from "./maintenance"

describe("expectedRestoreConfirmation", () => {
  it("uses the fixed human-readable confirmation phrase", () => {
    expect(expectedRestoreConfirmation()).toBe("RESTORE DATABASE")
  })
})
