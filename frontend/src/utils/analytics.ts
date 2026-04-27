export function formatPercent(value: number | null | undefined, fractionDigits = 1) {
  if (value === null || value === undefined) {
    return "N/A"
  }

  return `${(value * 100).toFixed(fractionDigits)}%`
}

export function formatHourLabel(hour: number) {
  return hour.toString().padStart(2, "0")
}

export function truncateLabel(label: string, maxLength = 18) {
  if (label.length <= maxLength) {
    return label
  }

  return `${label.slice(0, maxLength - 3)}...`
}
