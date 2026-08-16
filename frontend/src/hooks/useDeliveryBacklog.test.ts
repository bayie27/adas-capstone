import { describe, expect, it } from "vitest"

import { useDeliveryBacklog } from "./useDeliveryBacklog"

describe("useDeliveryBacklog", () => {
  it("always returns null until G5 ships a real endpoint", () => {
    expect(useDeliveryBacklog()).toBeNull()
  })
})
