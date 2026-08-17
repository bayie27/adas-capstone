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
  /**
   * Whether the synchronous export just settled with an error. The caller
   * already computes this for its own `QueryErrorBanner` -- passed through
   * so the button can tell "finished" from "finished successfully" without
   * a second copy of that state.
   */
  exportHasError?: boolean
  className?: string
  /**
   * Phase 17 — when both ceilings are exceeded, an "over both limits" filter
   * set otherwise has nowhere to go. Passing this activates the async job
   * fallback in place of the static "too large" paragraph; omitting it keeps
   * the exact prior behaviour, so every caller that predates Phase 17
   * (Dashboard, Detections, AI Performance, Audit Log all passed no
   * job-related prop before this) needs no change to keep working.
   */
  onExportJob?: (format: ExportFormat) => void | Promise<unknown>
  isSubmittingJob?: boolean
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
  exportHasError,
  className,
  onExportJob,
  isSubmittingJob,
}: ExportButtonProps) {
  const [open, setOpen] = useState(false)
  // §2.8's "swap the label for the present-progressive verb" idiom, carried
  // one step further: a synchronous export gives no other sign it did
  // anything (the file just appears in the browser's own download UI), so
  // the button flashes a past-tense label the same way it shows a
  // present-progressive one while in flight. Scoped to `isExporting`, not
  // `isSubmittingJob` -- queuing a background job isn't "the file is ready".
  const [justExported, setJustExported] = useState(false)
  const wasExporting = useRef(false)
  // `position: fixed` + coordinates measured off the trigger, not
  // `absolute` + `right-0` on a statically-positioned ancestor chain.
  // Root cause: this menu sits inside <main>, which never establishes its
  // own stacking context (no transform/opacity/isolation anywhere between
  // it and <body>), so its z-index is compared against the Sidebar's
  // `position: fixed` in the root stacking context — where Chromium's
  // compositor promotes `position: fixed` descendants of the shell's
  // `overflow-hidden` flex row to a layer no `position: absolute`
  // z-index, however high, can paint above. Matching the Sidebar's own
  // `position: fixed` escapes that trap; verified live against the
  // running app before writing this fix.
  const [menuPosition, setMenuPosition] = useState<{ top: number; right: number } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  function toggleOpen() {
    if (!open && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect()
      setMenuPosition({ top: rect.bottom + 4, right: window.innerWidth - rect.right })
    }
    setOpen((prev) => !prev)
  }

  useEffect(() => {
    if (!open) return

    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false)
    }
    // A `position: fixed` menu doesn't track the page under it — close
    // rather than let it drift out from under the trigger on scroll.
    function onScroll() {
      setOpen(false)
    }

    document.addEventListener("mousedown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    window.addEventListener("scroll", onScroll, true)
    return () => {
      document.removeEventListener("mousedown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
      window.removeEventListener("scroll", onScroll, true)
    }
  }, [open])

  useEffect(() => {
    const justFinishedCleanly = wasExporting.current && !isExporting && !exportHasError
    wasExporting.current = Boolean(isExporting)

    if (justFinishedCleanly) {
      setJustExported(true)
      const timer = setTimeout(() => setJustExported(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [isExporting, exportHasError])

  async function choose(format: ExportFormat) {
    setOpen(false)
    await onExport(format)
  }

  async function chooseJob(format: ExportFormat) {
    setOpen(false)
    await onExportJob?.(format)
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
        onClick={toggleOpen}
      >
        <RiDownloadLine size={13} />
        {justExported ? "Exported" : "Export"}
        <RiArrowDownSLine size={14} aria-hidden />
      </Button>

      {open && menuPosition ? (
        <div
          role="menu"
          aria-label="Export format"
          style={{ top: menuPosition.top, right: menuPosition.right }}
          className="fixed z-20 w-64 overflow-hidden rounded-md border border-stroke bg-surface-1 shadow-overlay"
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
            Over BOTH ceilings, the synchronous routes have nowhere to send
            the operator. Phase 17 gives them a real path: the async job
            route has no row limit at all, so either format works — as long
            as a caller opted in by passing onExportJob. A caller that
            hasn't (yet) keeps the exact prior static paragraph.
          */}
          {allBlocked && onExportJob ? (
            <div className="border-t border-stroke px-3 py-2">
              <p className="mb-1.5 text-[10px] text-fg-muted">
                Too large to export directly. Run it as a background job instead — this has no row
                limit.
              </p>
              <div className="flex gap-2">
                {(["csv", "pdf"] as ExportFormat[]).map((format) => (
                  <button
                    key={format}
                    type="button"
                    disabled={isSubmittingJob}
                    onClick={() => chooseJob(format)}
                    className={cn(
                      "rounded-sm border border-stroke px-2 py-1 text-[10px] font-medium text-fg-body",
                      "transition-colors duration-150 hover:bg-surface-2",
                      "disabled:cursor-not-allowed disabled:opacity-60",
                    )}
                  >
                    Run as a background job ({format.toUpperCase()})
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {allBlocked && !onExportJob ? (
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
