import { useEffect, useRef, useState } from "react"
import { RiArrowDownSLine, RiDownloadLine } from "@remixicon/react"

import { Button } from "@/components/ui/Button"
import { cn } from "@/utils/cn"

export type ExportFormat = "csv" | "pdf"

/**
 * The shared export control: one primary button that opens a two-item format
 * menu.
 *
 * All four export routes accept `?format=csv|pdf` and no frontend helper had
 * ever sent it, so every export in the app was CSV — not because PDF was
 * unbuilt but because the client's own function signatures had no word for it.
 *
 * **The format is a real request parameter, not a filename suffix.** It goes on
 * the query string and the backend picks the renderer; a CSV renamed `.pdf`
 * would be the failure this replaces.
 *
 * Built here as a primitive rather than a flag on Detections because Phases 8,
 * 9, 16 and 17 need the identical control on Dashboard, AI Performance, Audit
 * Log and the job fallback.
 */

/**
 * `EXPORT_PDF_MAX_ROWS` and `EXPORT_CSV_MAX_ROWS` from `app/core/config.py`.
 *
 * The ceilings are **asymmetric by a factor of five**, which is the whole
 * reason the pre-flight shows them separately: the same filter set can be a
 * perfectly good CSV and a 413 as a PDF.
 */
const ROW_LIMIT: Record<ExportFormat, number> = {
  pdf: 10_000,
  csv: 50_000,
}

interface ExportButtonProps {
  onExport: (format: ExportFormat) => void | Promise<unknown>
  /**
   * Rows the active filter set would export.
   *
   * **`undefined` means unknown, not zero.** A screen that cannot cheaply
   * count its rows (Dashboard returns aggregates, not a filtered row count)
   * passes nothing and gets no pre-flight — an unknown count must never render
   * as an all-clear, because a false all-clear is worse than no guidance.
   */
  rowCount?: number
  /** Disables the trigger entirely, e.g. while a query is still loading. */
  disabled?: boolean
  isExporting?: boolean
  className?: string
}

const FORMAT_LABEL: Record<ExportFormat, string> = {
  csv: "Export as CSV",
  pdf: "Export as PDF",
}

const ROWS = new Intl.NumberFormat("en-US")

export function ExportButton({
  onExport,
  rowCount,
  disabled,
  isExporting,
  className,
}: ExportButtonProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return

    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false)
    }

    document.addEventListener("mousedown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("mousedown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [open])

  async function choose(format: ExportFormat) {
    setOpen(false)
    await onExport(format)
  }

  // `undefined` short-circuits every check below: unknown stays unknown.
  const overLimit = (format: ExportFormat) => rowCount !== undefined && rowCount > ROW_LIMIT[format]

  const allBlocked = overLimit("csv") && overLimit("pdf")

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <Button
        variant="primary"
        size="sm"
        disabled={disabled}
        isLoading={isExporting}
        loadingLabel="Exporting…"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        <RiDownloadLine size={13} />
        Export
        <RiArrowDownSLine size={14} aria-hidden />
      </Button>

      {open ? (
        <div
          role="menu"
          aria-label="Export format"
          className="absolute right-0 z-20 mt-1 w-64 overflow-hidden rounded-md border border-stroke bg-surface-1 shadow-overlay"
        >
          {(["csv", "pdf"] as ExportFormat[]).map((format) => {
            const blocked = overLimit(format)
            return (
              <button
                key={format}
                type="button"
                role="menuitem"
                disabled={blocked}
                onClick={() => choose(format)}
                className={cn(
                  "flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-xs transition-colors duration-150",
                  blocked
                    ? "cursor-not-allowed text-fg-muted opacity-60"
                    : "text-fg-body hover:bg-surface-2",
                )}
              >
                <span>{FORMAT_LABEL[format]}</span>
                {blocked ? (
                  <span className="text-[10px] text-warning">
                    {ROWS.format(ROW_LIMIT[format])} row limit — {ROWS.format(rowCount as number)}{" "}
                    rows in this filter
                  </span>
                ) : null}
              </button>
            )
          })}

          {/*
            Over BOTH ceilings there is nowhere to send the operator yet. The
            async job route is Phase 17's surface and does not exist, so this
            states the problem and stops — telling them before they wait for a
            413 is the whole point, and offering a path that isn't built would
            be worse than offering none.
          */}
          {allBlocked ? (
            <p className="border-t border-stroke px-3 py-2 text-[10px] text-fg-muted">
              This filter set is too large to export directly. Narrow the date range or the camera
              filter and try again.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
