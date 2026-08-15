import type { IncidentHandledInfo } from "@/api/alerts"
import { formatFullDateTime } from "@/utils/datetime"

/**
 * "Already handled by another operator" — one presentation, two sources.
 *
 * `routes/alerts.py:_conflict_response` returns `current_status`,
 * `handled_action`, `handled_by` and `handled_at` on a 409 CONFLICT_STATE, and
 * its docstring calls that "the exact 409 body the frontend's already-handled
 * modal depends on". The same four ride the `ALERT_STATUS_UPDATE` broadcast.
 *
 * The distinction matters and is why this is shared rather than inlined at the
 * 409 call site: **the 409 reaches only the operator who lost the race**,
 * while **the broadcast reaches everyone**. Rendering them differently would
 * mean two operators watching one incident get two different accounts of what
 * just happened to it.
 */

const ACTION_VERB: Record<string, string> = {
  confirm: "confirmed",
  dismiss: "dismissed",
  resolve: "resolved",
  snooze: "snoozed",
}

function sentence(info: IncidentHandledInfo): string {
  const verb = info.handledAction ? (ACTION_VERB[info.handledAction] ?? "handled") : "handled"
  const who = info.handledBy ?? "another operator"
  return `${who} ${verb} this incident.`
}

export function IncidentHandledNotice({
  info,
  tone = "warning",
}: {
  info: IncidentHandledInfo
  /** `warning` when this operator lost a race; `neutral` for a passive update. */
  tone?: "warning" | "neutral"
}) {
  const toneClass =
    tone === "warning"
      ? "border-warning-border bg-warning-subtle text-warning"
      : "border-stroke bg-surface-3 text-fg-muted"

  return (
    <div className={`mb-4 rounded-md border px-3 py-2 ${toneClass}`}>
      <p className="text-xs font-medium first-letter:uppercase">{sentence(info)}</p>
      <p className="mt-1 text-[10px] text-fg-muted">
        {info.currentStatus ? `Now ${info.currentStatus}` : "Status changed"}
        {info.handledAt ? ` · ${formatFullDateTime(info.handledAt)}` : null}
      </p>
    </div>
  )
}
