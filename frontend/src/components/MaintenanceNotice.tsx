import { RiAlertLine, RiCloseLine } from "@remixicon/react"

import { useMaintenanceStore } from "@/store/useMaintenanceStore"
import { focusRing } from "@/components/ui/Button"
import { cn } from "@/utils/cn"

/**
 * A dismissable banner across the top of the app for MAINTENANCE_NOTICE —
 * broadcast just before a restore takes the backend offline, so a socket
 * drop the operator would otherwise read as a crash gets an explanation
 * first. No Figma frame; reuses the §2.8 banner treatment (warning tone —
 * this is a courtesy warning, not the danger/error shape) rather than
 * inventing a new one.
 *
 * Deliberately a banner, not a toast (easy to miss) or a modal (would block
 * an operator who may be mid-incident). Sits below GlobalAlerts in the
 * stacking order — the alarm dialog is the one thing this must never cover.
 */
export function MaintenanceNotice() {
  const notice = useMaintenanceStore((state) => state.notice)
  const dismiss = useMaintenanceStore((state) => state.dismiss)

  if (!notice) return null

  return (
    <div role="status" className="fixed inset-x-0 top-0 z-[9998]">
      <div className="flex items-center justify-between gap-3 border-b border-warning-border bg-warning-subtle px-4 py-2.5 text-caption text-warning">
        <span className="flex min-w-0 items-center gap-2">
          <RiAlertLine size={15} className="shrink-0" aria-hidden="true" />
          {/* Server-authored copy, rendered verbatim — this frontend does
              not compose its own sentence around it. */}
          <span className="truncate">
            {notice.message}
            {notice.backup_id ? (
              <span className="text-warning/70"> (Backup: {notice.backup_id})</span>
            ) : null}
          </span>
        </span>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss maintenance notice"
          className={cn(
            "shrink-0 rounded-sm text-warning transition-colors duration-150 hover:text-fg",
            focusRing,
          )}
        >
          <RiCloseLine size={16} />
        </button>
      </div>
    </div>
  )
}
