import type { AlertLog, AlertStatus } from "@/api/alerts"
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
    return "text-warning"
  }

  if (status === "Resolved") {
    return "text-success"
  }

  if (status === "Unverified") {
    return "text-fg"
  }

  return "text-fg-muted"
}

export function getAlertBadgeClass(status: AlertStatus) {
  if (status === "Ongoing") {
    return "bg-warning text-fg-on-primary"
  }

  if (status === "Resolved") {
    return "bg-success text-fg-on-primary"
  }

  if (status === "Unverified") {
    return "bg-primary text-fg-on-primary"
  }

  return "bg-surface-3 text-fg"
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
