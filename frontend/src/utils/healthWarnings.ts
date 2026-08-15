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

  return { label: warning.code, message: warning.code, tone }
}
