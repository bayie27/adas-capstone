import type { HealthWarning } from "@/api/health"
import type { StatusTone } from "@/components/ui/statusTone"

/**
 * `warnings[]` carries `{code, severity, measurement, threshold}` with **no
 * presentation strings** — the backend's deliberate choice, so this table is
 * the frontend's entire copy surface for it. Five codes are emitted today.
 */
const WARNING_COPY: Record<
  string,
  { label: string; describe: (measurement: number | null, threshold: number | null) => string }
> = {
  GPU_TEMP_CRITICAL: {
    label: "GPU Temperature",
    describe: (m, t) => `GPU running at ${m ?? "N/A"}°C, above the ${t ?? "N/A"}°C limit.`,
  },
  RAM_CRITICAL: {
    label: "Memory",
    describe: (m, t) => `Memory usage at ${m ?? "N/A"}%, above the ${t ?? "N/A"}% limit.`,
  },
  DISK_CRITICAL: {
    label: "Disk Space",
    describe: (m, t) => `Disk usage at ${m ?? "N/A"}%, above the ${t ?? "N/A"}% limit.`,
  },
  DISK_WARNING: {
    label: "Disk Space",
    describe: (m, t) => `Disk usage at ${m ?? "N/A"}%, approaching the ${t ?? "N/A"}% limit.`,
  },
  // `measurement` is a literal 0 here — "no camera reported" — and must never
  // be read as a rate or a temperature.
  AI_HEARTBEAT_STALE: {
    label: "AI Engine",
    describe: (_m, t) =>
      `No camera has reported in over ${t ?? "N/A"}s — the AI engine may be down.`,
  },
}

/**
 * Three more codes are proposed against the backend and not yet emitted:
 * OUTBOX_QUARANTINED (Q15), CAPACITY_EXCEEDED (Q16), ENGINE_CLOCK_SKEW
 * (Q17). This is deliberately not a switch over the five known codes — a
 * switch means every new code needs a frontend change to appear at all.
 * The fallback below is what makes those three (and anything else the
 * backend ever adds) cost zero frontend work the day it starts emitting.
 */
export function humanizeWarningCode(code: string): string {
  return code
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

export interface DescribedWarning {
  label: string
  message: string
  tone: StatusTone
}

const SEVERITY_TONE: Record<string, StatusTone> = {
  warning: "warning",
  critical: "danger",
}

export function describeWarning(warning: HealthWarning): DescribedWarning {
  const entry = WARNING_COPY[warning.code]
  const tone = SEVERITY_TONE[warning.severity] ?? "neutral"

  if (entry) {
    return {
      label: entry.label,
      message: entry.describe(warning.measurement, warning.threshold),
      tone,
    }
  }

  // The open fallback: a code the client has never seen still gets a
  // humanised label and its numbers, rather than being dropped or shown as
  // its own raw SCREAMING_SNAKE_CASE.
  const label = humanizeWarningCode(warning.code)
  const message =
    warning.measurement !== null && warning.threshold !== null
      ? `${label}: ${warning.measurement} (limit ${warning.threshold})`
      : label

  return { label, message, tone }
}
