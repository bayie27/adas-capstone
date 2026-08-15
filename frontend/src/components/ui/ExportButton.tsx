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

interface ExportButtonProps {
  onExport: (format: ExportFormat) => void | Promise<unknown>
  /** Disables the trigger entirely, e.g. while a query is still loading. */
  disabled?: boolean
  isExporting?: boolean
  className?: string
}

const FORMAT_LABEL: Record<ExportFormat, string> = {
  csv: "Export as CSV",
  pdf: "Export as PDF",
}

export function ExportButton({ onExport, disabled, isExporting, className }: ExportButtonProps) {
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
          {(["csv", "pdf"] as ExportFormat[]).map((format) => (
            <button
              key={format}
              type="button"
              role="menuitem"
              onClick={() => choose(format)}
              className="flex w-full items-center justify-between px-3 py-2 text-left text-xs text-fg-body transition-colors duration-150 hover:bg-surface-2"
            >
              <span>{FORMAT_LABEL[format]}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
