const PHILIPPINE_OFFSET = "+08:00"

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
