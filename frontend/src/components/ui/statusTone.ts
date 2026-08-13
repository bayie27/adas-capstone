import type { AlertStatus } from "@/api/alerts"
import type { CameraAiStatus, CameraConnectionStatus } from "@/api/cameras"

/**
 * The one place a domain status becomes a colour.
 *
 * This replaces the five class-lookup helpers in utils — presentation logic
 * living in a utils module, returning Tailwind class strings, which is where
 * hardcoded colour hides best. §2.2 assigns the meanings:
 *
 *   success  Connected, Active, Resolved
 *   warning  Reconnecting, Paused, Ongoing
 *   danger   Disconnected, Unresponsive, Inactive
 *   neutral  Dismissed, and anything terminal without a signal
 *   default  Unverified — plain foreground, see below
 *
 * Getting one of these backwards makes a broken camera read as healthy, so
 * the mapping is a single table rather than five if-chains.
 *
 * Split out of StatusText.tsx because react-refresh requires a component file
 * to export only components.
 */
export type StatusTone = "default" | "neutral" | "success" | "warning" | "danger"

export const TONE_CLASS: Record<StatusTone, string> = {
  default: "text-fg",
  neutral: "text-fg-muted",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
}

export function getAlertStatusTone(status: AlertStatus): StatusTone {
  if (status === "Ongoing") return "warning"
  if (status === "Resolved") return "success"
  // Unverified reads as plain foreground rather than a semantic colour — the
  // alert dialog is already carrying the alarm — and Dismissed recedes to
  // muted. This matches what the pages render today, so the screen phases
  // inherit the same mapping rather than a silently changed one.
  if (status === "Unverified") return "default"
  return "neutral"
}

export function getCameraConnectionTone(status: CameraConnectionStatus): StatusTone {
  if (status === "Connected") return "success"
  if (status === "Reconnecting") return "warning"
  return "danger"
}

export function getCameraAiTone(status: CameraAiStatus): StatusTone {
  if (status === "Active") return "success"
  if (status === "Paused") return "warning"
  return "danger"
}
