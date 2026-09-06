const PHILIPPINE_OFFSET = "+08:00"
const PHILIPPINE_TIME_ZONE = "Asia/Manila"

/** Convert a native date-input value into the first instant of that Philippine day. */
export function toPhilippineDayStart(value: string): string | undefined {
  return value ? `${value}T00:00:00${PHILIPPINE_OFFSET}` : undefined
}

/** Convert a native date-input value into the inclusive final instant of that Philippine day. */
export function toPhilippineDayEnd(value: string): string | undefined {
  return value ? `${value}T23:59:59.999999${PHILIPPINE_OFFSET}` : undefined
}

/** Date-input values are ISO calendar dates, so lexical ordering is chronological ordering. */
export function isReversedDateRange(start: string, end: string): boolean {
  return Boolean(start && end && start > end)
}

/**
 * Today's calendar date in the Philippines, regardless of the operator's own
 * system clock/timezone — quick-range presets ("Today", "Last 7 days") are
 * meaningless if they drift onto a different Philippine day than the one the
 * rest of this module already assumes every `value` string represents.
 */
export function getPhilippineToday(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: PHILIPPINE_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date())
  const lookup = Object.fromEntries(parts.map(({ type, value }) => [type, value]))
  return `${lookup.year}-${lookup.month}-${lookup.day}`
}

/**
 * `value` plus/minus `days`, done on a UTC-anchored Date so the calendar
 * arithmetic can't be shifted a day by the browser's own local timezone
 * (the same class of bug `toPhilippineDayStart`/`-End` avoid — see the
 * leap-day case in dateRange.test.ts).
 */
export function addCalendarDays(value: string, days: number): string {
  const [year, month, day] = value.split("-").map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  date.setUTCDate(date.getUTCDate() + days)
  return toCalendarDateString(date)
}

/**
 * The inclusive 7-day window ending today, in Philippine calendar days.
 * `today` defaults to `getPhilippineToday()`; a caller that already computed
 * it (DateRangePicker builds every preset off one shared `today`) can pass it
 * through instead of asking `Intl` twice for the same instant.
 */
export function getLastSevenDaysRange(today: string = getPhilippineToday()): {
  start: string
  end: string
} {
  return { start: addCalendarDays(today, -6), end: today }
}

/** The first day of `value`'s month, same UTC-anchored arithmetic as `addCalendarDays`. */
export function startOfCalendarMonth(value: string): string {
  const [year, month] = value.split("-").map(Number)
  return toCalendarDateString(new Date(Date.UTC(year, month - 1, 1)))
}

/**
 * The number of calendar days in `[start, end]`, both ends included --
 * `getLastSevenDaysRange()`'s own window (today minus 6, through today)
 * must come back as 7, not 6. Same UTC-anchored arithmetic as
 * `addCalendarDays`, so a DST-observing host clock can't shift it by an
 * hour and round to the wrong day count.
 */
export function daysBetweenInclusive(start: string, end: string): number {
  const [startYear, startMonth, startDay] = start.split("-").map(Number)
  const [endYear, endMonth, endDay] = end.split("-").map(Number)
  const startUtc = Date.UTC(startYear, startMonth - 1, startDay)
  const endUtc = Date.UTC(endYear, endMonth - 1, endDay)
  return Math.round((endUtc - startUtc) / (24 * 60 * 60 * 1000)) + 1
}

function toCalendarDateString(date: Date): string {
  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, "0")
  const day = String(date.getUTCDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}
