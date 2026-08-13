import type { AlertLog, AlertStatus } from "@/types/alerts"
import { formatFullDateTime } from "@/utils/datetime"

export function formatAlertCode(logId: number) {
  return `ACC-${logId.toString().padStart(6, "0")}`
}

export function formatAlertConfidence(score: number) {
  return `${(score * 100).toFixed(1)}%`
}

export function getAlertLastHandledBy(alert: AlertLog) {
  if (alert.closed_by_name) {
    return alert.closed_by_name
  }

  if (alert.verified_by_name) {
    return alert.verified_by_name
  }

  return "-"
}

export function getAlertLastUpdated(alert: AlertLog) {
  if (alert.closed_at) {
    return formatFullDateTime(alert.closed_at)
  }

  if (alert.verified_at) {
    return formatFullDateTime(alert.verified_at)
  }

  return "-"
}

export function getAlertStatusTextClass(status: AlertStatus) {
  if (status === "Ongoing") {
    return "text-amber-500"
  }

  if (status === "Resolved") {
    return "text-emerald-500"
  }

  if (status === "Unverified") {
    return "text-white"
  }

  return "text-fg-muted"
}

export function getAlertBadgeClass(status: AlertStatus) {
  if (status === "Ongoing") {
    return "bg-amber-500 text-black"
  }

  if (status === "Resolved") {
    return "bg-emerald-500 text-black"
  }

  if (status === "Unverified") {
    return "bg-white text-black"
  }

  return "bg-surface-3 text-white"
}

export function getAlertBorderClass(status: AlertStatus) {
  if (status === "Ongoing") {
    return "border-t-amber-500"
  }

  if (status === "Resolved") {
    return "border-t-emerald-500"
  }

  if (status === "Unverified") {
    return "border-t-white"
  }

  return "border-t-fg-muted"
}
