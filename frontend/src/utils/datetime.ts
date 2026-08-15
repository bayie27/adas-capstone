// Module-level formatters: `Intl.*Format` construction is expensive (locale
// data resolution), so build each once per session instead of per table cell
// per render.
const FULL = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
})

const SHORT = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
})

const RELATIVE = new Intl.RelativeTimeFormat("en", { numeric: "auto" })

function parse(value: string | null | undefined): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatFullDateTime(value: string | null | undefined) {
  const date = parse(value)
  return date ? FULL.format(date) : "-"
}

export function formatShortDateTime(value: string | null | undefined) {
  const date = parse(value)
  return date ? SHORT.format(date) : "-"
}

/**
 * How far in the past `value` is, in seconds, or `null` if it is unparseable
 * or in the future. `nowMs` is passed in rather than read from `Date.now()`
 * so a caller driving it from `useNow` re-renders on the same tick it
 * measures against.
 */
export function secondsSince(value: string | null | undefined, nowMs: number): number | null {
  const date = parse(value)
  if (!date) return null
  const seconds = Math.floor((nowMs - date.getTime()) / 1000)
  return seconds < 0 ? null : seconds
}

/** "12 minutes", "3 hours", "45 seconds" — a bare duration, no direction. */
export function formatDuration(totalSeconds: number): string {
  if (totalSeconds < 60) {
    return `${totalSeconds} second${totalSeconds === 1 ? "" : "s"}`
  }

  const minutes = Math.floor(totalSeconds / 60)
  if (minutes < 60) {
    return `${minutes} minute${minutes === 1 ? "" : "s"}`
  }

  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return `${hours} hour${hours === 1 ? "" : "s"}`
  }

  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? "" : "s"}`
}

export function formatRelativeDateTime(value: string | null | undefined) {
  if (!value) {
    return "Never"
  }

  const date = parse(value)
  if (!date) {
    return "-"
  }

  const diffMinutes = Math.round((date.getTime() - Date.now()) / 60000)

  if (Math.abs(diffMinutes) < 1) {
    return "Just now"
  }

  if (Math.abs(diffMinutes) < 60) {
    return RELATIVE.format(diffMinutes, "minute")
  }

  const diffHours = Math.round(diffMinutes / 60)

  if (Math.abs(diffHours) < 24) {
    return RELATIVE.format(diffHours, "hour")
  }

  const diffDays = Math.round(diffHours / 24)

  if (Math.abs(diffDays) < 7) {
    return RELATIVE.format(diffDays, "day")
  }

  return formatShortDateTime(value)
}
