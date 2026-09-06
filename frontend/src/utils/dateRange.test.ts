import { afterEach, describe, expect, it, vi } from "vitest"

import {
  addCalendarDays,
  daysBetweenInclusive,
  getLastSevenDaysRange,
  getPhilippineToday,
  isReversedDateRange,
  startOfCalendarMonth,
  toPhilippineDayEnd,
  toPhilippineDayStart,
} from "@/utils/dateRange"

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

describe("Calendar-day arithmetic for the quick-range presets", () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it("reads today as the Philippine calendar day, not the host's local day", () => {
    // 2026-08-30T16:00:00Z is already 2026-08-31 00:00 in Manila (+08:00) —
    // any implementation that let the host's own timezone leak in would
    // report the 30th here instead.
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-08-30T16:00:00Z"))
    expect(getPhilippineToday()).toBe("2026-08-31")
  })

  it("adds and subtracts days across a month boundary", () => {
    expect(addCalendarDays("2026-08-30", 1)).toBe("2026-08-31")
    expect(addCalendarDays("2026-08-31", 1)).toBe("2026-09-01")
    expect(addCalendarDays("2026-09-01", -1)).toBe("2026-08-31")
    expect(addCalendarDays("2026-08-16", 0)).toBe("2026-08-16")
  })

  it("finds the first day of the month regardless of which day it's asked from", () => {
    expect(startOfCalendarMonth("2026-08-30")).toBe("2026-08-01")
    expect(startOfCalendarMonth("2026-08-01")).toBe("2026-08-01")
  })

  it("builds the inclusive 7-day window ending today from an explicit today", () => {
    expect(getLastSevenDaysRange("2026-09-05")).toEqual({ start: "2026-08-30", end: "2026-09-05" })
  })

  it("defaults to the Philippine calendar day when today isn't passed in", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-09-05T04:00:00Z"))
    expect(getLastSevenDaysRange()).toEqual({ start: "2026-08-30", end: "2026-09-05" })
  })

  it("counts both ends of the range, matching the 'last 7 days' preset's own window", () => {
    const { start, end } = getLastSevenDaysRange("2026-09-05")
    expect(daysBetweenInclusive(start, end)).toBe(7)
  })

  it("counts a single selected day as 1, not 0", () => {
    expect(daysBetweenInclusive("2026-08-30", "2026-08-30")).toBe(1)
  })

  it("counts across a month boundary", () => {
    expect(daysBetweenInclusive("2026-08-30", "2026-09-02")).toBe(4)
  })
})
