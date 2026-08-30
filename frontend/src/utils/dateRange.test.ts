import { describe, expect, it } from "vitest"

import { isReversedDateRange, toPhilippineDayEnd, toPhilippineDayStart } from "@/utils/dateRange"

describe("Philippine date-range API bounds", () => {
  it("maps a selected day to offset-aware inclusive API bounds", () => {
    expect(toPhilippineDayStart("2026-08-30")).toBe("2026-08-30T00:00:00+08:00")
    expect(toPhilippineDayEnd("2026-08-30")).toBe("2026-08-30T23:59:59.999999+08:00")
  })

  it("omits empty open-ended bounds", () => {
    expect(toPhilippineDayStart("")).toBeUndefined()
    expect(toPhilippineDayEnd("")).toBeUndefined()
  })

  it("preserves a leap-day date without browser-local conversion", () => {
    expect(toPhilippineDayStart("2028-02-29")).toBe("2028-02-29T00:00:00+08:00")
    expect(toPhilippineDayEnd("2028-02-29")).toBe("2028-02-29T23:59:59.999999+08:00")
  })

  it("recognizes only a completed reversed ISO date range", () => {
    expect(isReversedDateRange("2026-08-31", "2026-08-30")).toBe(true)
    expect(isReversedDateRange("2026-08-30", "2026-08-30")).toBe(false)
    expect(isReversedDateRange("2026-08-30", "")).toBe(false)
  })
})
