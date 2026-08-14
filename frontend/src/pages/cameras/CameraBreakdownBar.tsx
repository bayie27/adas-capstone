import type {
  CameraAiBreakdown,
  CameraAiStatus,
  CameraBreakdowns,
  CameraConnectionBreakdown,
  CameraConnectionStatus,
} from "@/api/cameras"
import { BadgeDot } from "@/components/ui/Badge"
import {
  getCameraAiTone,
  getCameraConnectionTone,
  type StatusTone,
} from "@/components/ui/statusTone"

/**
 * `GET /api/cameras/` has always returned a `breakdowns` object beside
 * `kpis` — how the whole active population splits across the four connection
 * states and the four AI states — and nothing has ever rendered it. The three
 * KPI cards answer "how many are healthy"; they cannot answer "and what is
 * wrong with the rest", which is the question an operator opens this screen
 * with. Figma draws no such element, so this follows the screen's own idiom:
 * the tone mapping the status column already uses, and no new request.
 *
 * Deliberately NOT clickable, though every instinct says a count should lead
 * to its rows. `breakdowns` counts *presented* status — staleness-aware, the
 * same computation the table renders — while `GET /api/cameras/`'s
 * `ai_status` / `connection_status` filters compare the *stored* columns.
 * The two disagree whenever a camera has gone stale, which is most of them
 * when the AI engine is down: "Unresponsive 5" would filter to zero rows, and
 * "Inactive 1" to four. Wiring these up would make a correct count open an
 * incorrect list. Closing that gap is a backend change (filtering on
 * presented status), recorded in FE_Implementation.md rather than papered
 * over here.
 */

/**
 * Status-to-bucket-key pairs, written out rather than derived by lowercasing
 * the status: this way a renamed key on either side is a compile error
 * instead of a chip that silently reads 0 forever.
 */
const CONNECTION_ROWS: Array<{
  status: CameraConnectionStatus
  key: keyof CameraConnectionBreakdown
}> = [
  { status: "Connected", key: "connected" },
  { status: "Reconnecting", key: "reconnecting" },
  { status: "Disconnected", key: "disconnected" },
  { status: "Unresponsive", key: "unresponsive" },
]

const AI_ROWS: Array<{ status: CameraAiStatus; key: keyof CameraAiBreakdown }> = [
  { status: "Active", key: "active" },
  { status: "Paused", key: "paused" },
  { status: "Inactive", key: "inactive" },
  { status: "Unresponsive", key: "unresponsive" },
]

function BreakdownCount({
  label,
  tone,
  count,
}: {
  label: string
  tone: StatusTone
  count: number
}) {
  return (
    <span className="flex items-center gap-1.5 px-1 text-caption text-fg-muted">
      <BadgeDot tone={tone === "default" ? "neutral" : tone} />
      {label}
      <span className="font-medium text-fg">{count}</span>
    </span>
  )
}

export function CameraBreakdownBar({ breakdowns }: { breakdowns: CameraBreakdowns | undefined }) {
  if (!breakdowns) return null

  return (
    <div className="mb-6 flex flex-col gap-2.5 rounded-xl border border-stroke bg-surface-1 px-5 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="w-24 shrink-0 text-caption font-medium uppercase tracking-wider text-fg-muted">
          Connection
        </span>
        {CONNECTION_ROWS.map(({ status, key }) => (
          <BreakdownCount
            key={status}
            label={status}
            tone={getCameraConnectionTone(status)}
            count={breakdowns.connection[key]}
          />
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span className="w-24 shrink-0 text-caption font-medium uppercase tracking-wider text-fg-muted">
          AI Detection
        </span>
        {AI_ROWS.map(({ status, key }) => (
          <BreakdownCount
            key={status}
            label={status}
            tone={getCameraAiTone(status)}
            count={breakdowns.ai[key]}
          />
        ))}
      </div>
    </div>
  )
}
