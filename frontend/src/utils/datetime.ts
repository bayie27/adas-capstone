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
