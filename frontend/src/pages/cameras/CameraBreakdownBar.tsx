import type {
  CameraAiBreakdown,
  CameraAiStatus,
  CameraBreakdowns,
  CameraConnectionBreakdown,
  CameraConnectionStatus,
} from "@/api/cameras"
import { BadgeDot } from "@/components/ui/Badge"
import { focusRing } from "@/components/ui/Button"
import {
  getCameraAiTone,
  getCameraConnectionTone,
  type StatusTone,
} from "@/components/ui/statusTone"
import { cn } from "@/utils/cn"

/**
 * `GET /api/cameras/` has always returned a `breakdowns` object beside
 * `kpis` — how the whole active population splits across the four connection
 * states and the four AI states — and nothing has ever rendered it. The three
 * KPI cards answer "how many are healthy"; they cannot answer "and what is
 * wrong with the rest", which is the question an operator opens this screen
 * with. Figma draws no such element, so this follows the screen's own idiom:
 * the tone mapping the status column already uses, and no new request.
 *
 * Now clickable (P19 §2): `GET /api/cameras/`'s `ai_status`/`connection_status`
 * filters compare the same staleness-aware *presented* status `breakdowns`
 * itself counts and the table cells render, not the raw stored columns --
 * the mismatch that justified leaving these inert ("Unresponsive 5" filtering
 * to zero rows) no longer exists. Each count maps to the exact same status
 * string as its own label, single-select and toggling: clicking the active
 * count clears the filter, clicking a different one replaces it.
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
  isActive,
  onClick,
}: {
  label: string
  tone: StatusTone
  count: number
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isActive}
      className={cn(
        "flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1 text-caption text-fg-muted",
        "transition-colors duration-150 hover:bg-surface-2",
        isActive && "bg-primary/10 text-fg-body",
        focusRing,
      )}
    >
      <BadgeDot tone={tone === "default" ? "neutral" : tone} />
      {label}
      <span className="font-medium text-fg">{count}</span>
    </button>
  )
}

export function CameraBreakdownBar({
  breakdowns,
  activeConnectionStatus,
  activeAiStatus,
  onSelectConnectionStatus,
  onSelectAiStatus,
}: {
  breakdowns: CameraBreakdowns | undefined
  /** The single-select filter's current value, or `null` when unfiltered
   * ("all"). Used only to render the pressed state -- Cameras.tsx owns the
   * actual filter state. */
  activeConnectionStatus: CameraConnectionStatus | null
  activeAiStatus: CameraAiStatus | null
  /** Toggle semantics belong to the caller: clicking the already-active
   * status is expected to clear the filter, not re-select it -- this
   * component only ever reports "this status was clicked." */
  onSelectConnectionStatus: (status: CameraConnectionStatus) => void
  onSelectAiStatus: (status: CameraAiStatus) => void
}) {
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
            isActive={activeConnectionStatus === status}
            onClick={() => onSelectConnectionStatus(status)}
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
            isActive={activeAiStatus === status}
            onClick={() => onSelectAiStatus(status)}
          />
        ))}
      </div>
    </div>
  )
}
