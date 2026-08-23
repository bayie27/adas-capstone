import type { HealthWarning } from "@/api/health"

/**
 * Operator-facing copy for the five backend warning codes.
 *
 * The backend emits `{ code, severity, measurement, threshold }` with no
 * presentation strings (D-009 — the frontend controls copy). This module is
 * the single source of truth for the plain-language sentences a DRRMO
 * operator or Head of Operations reads in the top-level status banner.
 *
 * `tone` maps the backend's `severity` field to two display-side tiers:
 *   'bad'  → danger colors  (critical severity)
 *   'warn' → warning colors (warning severity)
 *
 * Do not inline operator-facing warning strings in JSX — extend this table
 * instead so future backend codes cost zero frontend work beyond an entry here.
 */
export interface OperatorWarningEntry {
  tone: "bad" | "warn"
  /** Short headline used in the banner primary line. */
  text: string
  /** One-sentence detail with measurement context, used in the expanded view. */
  detail: (measurement: number | null, threshold: number | null) => string
}

export const OPERATOR_WARNING_COPY: Record<string, OperatorWarningEntry> = {
  GPU_TEMP_CRITICAL: {
    tone: "bad",
    text: "Graphics processor is overheating",
    detail: (m, t) =>
      `The graphics processor is running at ${m ?? "N/A"}°C, above the safe limit of ${t ?? "N/A"}°C. Detection speed may drop or the system may restart.`,
  },
  RAM_CRITICAL: {
    tone: "bad",
    text: "System memory almost full",
    detail: (m, t) =>
      `System memory is ${m ?? "N/A"}% full (limit: ${t ?? "N/A"}%). This can cause slow response times or crashes.`,
  },
  DISK_CRITICAL: {
    tone: "bad",
    text: "Storage almost full",
    detail: (m, t) =>
      `Storage is ${m ?? "N/A"}% full (limit: ${t ?? "N/A"}%). New incident recordings may fail to save.`,
  },
  DISK_WARNING: {
    tone: "warn",
    text: "Storage getting full",
    detail: (m, t) =>
      `Storage is ${m ?? "N/A"}% full (approaching the ${t ?? "N/A"}% warning level). Consider freeing space soon.`,
  },
  AI_HEARTBEAT_STALE: {
    tone: "warn",
    text: "Cameras aren't reporting",
    detail: (_m, t) =>
      `No camera has sent a status update in over ${t ?? "N/A"} seconds. The AI detection system may have stopped.`,
  },
}

/**
 * Returns the operator-facing entry for a given warning, falling back to a
 * humanised version of the raw code for any future codes the backend adds
 * before the frontend is updated.
 */
export function getOperatorWarningEntry(warning: HealthWarning): OperatorWarningEntry & {
  detail: string
} {
  const entry = OPERATOR_WARNING_COPY[warning.code]
  if (entry) {
    return {
      ...entry,
      detail: entry.detail(warning.measurement, warning.threshold),
    }
  }

  // Open fallback: humanize SCREAMING_SNAKE_CASE so a new code is still
  // readable without requiring a frontend deployment.
  const humanized = warning.code
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")

  const detail =
    warning.measurement !== null && warning.threshold !== null
      ? `${humanized}: ${warning.measurement} (limit ${warning.threshold})`
      : humanized

  return {
    tone: warning.severity === "critical" ? "bad" : "warn",
    text: humanized,
    detail,
  }
}
