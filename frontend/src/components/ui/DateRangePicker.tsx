import { useEffect, useRef, useState } from "react"
import { RiCalendar2Line, RiCheckLine } from "@remixicon/react"

import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"
import { DateRangeCalendar } from "@/components/ui/DateRangeCalendar"
import {
  addCalendarDays,
  getLastSevenDaysRange,
  getPhilippineToday,
  startOfCalendarMonth,
} from "@/utils/dateRange"

type PresetKey = "today" | "7" | "30" | "month" | "custom"

const PRESETS: { key: Exclude<PresetKey, "custom">; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "7", label: "Last 7 days" },
  { key: "30", label: "Last 30 days" },
  { key: "month", label: "This month" },
]

const MONTH_SHORT = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
]

function computePresetRange(
  key: Exclude<PresetKey, "custom">,
  today: string,
): { start: string; end: string } {
  switch (key) {
    case "today":
      return { start: today, end: today }
    case "7":
      return getLastSevenDaysRange(today)
    case "30":
      return { start: addCalendarDays(today, -29), end: today }
    case "month":
      return { start: startOfCalendarMonth(today), end: today }
  }
}

/** Which preset (if any) the committed start/end exactly reproduce, so the popover can highlight it and the trigger can show its name instead of a raw date range. */
function matchPreset(start: string, end: string, today: string): PresetKey | null {
  if (!start || !end) return null
  const match = PRESETS.find((preset) => {
    const range = computePresetRange(preset.key, today)
    return range.start === start && range.end === end
  })
  return match?.key ?? null
}

function formatDisplayDate(iso: string, withYear: boolean): string {
  const [year, month, day] = iso.split("-").map(Number)
  return withYear ? `${MONTH_SHORT[month - 1]} ${day}, ${year}` : `${MONTH_SHORT[month - 1]} ${day}`
}

function formatRangeLabel(start: string, end: string): string {
  if (start === end) return formatDisplayDate(start, true)
  return `${formatDisplayDate(start, false)} – ${formatDisplayDate(end, true)}`
}

/**
 * A trigger button that opens a popover: quick presets (Today, Last 7 days,
 * Last 30 days, This month) commit on a single click, and "Custom range"
 * reveals a two-click range calendar with its own Cancel/Apply — replacing
 * the two independent native `<input type="date">` fields this control used
 * to render. The external contract (controlled ISO `start`/`end` strings,
 * `onStartChange`/`onEndChange`) is unchanged, so callers need no changes.
 */
export function DateRangePicker({
  start,
  end,
  onStartChange,
  onEndChange,
  disabled = false,
  label = "Date range",
  className,
}: {
  /** ISO `yyyy-mm-dd`, or "" for open-ended. */
  start: string
  end: string
  onStartChange: (value: string) => void
  onEndChange: (value: string) => void
  disabled?: boolean
  label?: string
  className?: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)

  const [open, setOpen] = useState(false)
  const [pendingMode, setPendingMode] = useState<PresetKey>("custom")
  const [pendingStart, setPendingStart] = useState<string | null>(null)
  const [pendingEnd, setPendingEnd] = useState<string | null>(null)
  const [pickAnchor, setPickAnchor] = useState<string | null>(null)
  const [viewYear, setViewYear] = useState(0)
  const [viewMonth, setViewMonth] = useState(0)

  useEffect(() => {
    if (!open) return
    const handleOutsideClick = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", handleOutsideClick)
    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick)
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [open])

  const today = getPhilippineToday()
  const matchedPreset = matchPreset(start, end, today)
  const triggerLabel =
    !start || !end
      ? "Select date range"
      : (PRESETS.find((preset) => preset.key === matchedPreset)?.label ??
        formatRangeLabel(start, end))

  function openPopover() {
    const seedStart = start || null
    const seedEnd = end || null
    setPendingStart(seedStart)
    setPendingEnd(seedEnd)
    setPickAnchor(null)
    setPendingMode(
      seedStart && seedEnd ? (matchPreset(seedStart, seedEnd, today) ?? "custom") : "custom",
    )
    const [year, month] = (seedStart ?? today).split("-").map(Number)
    setViewYear(year)
    setViewMonth(month - 1)
    setOpen(true)
  }

  function choosePreset(key: Exclude<PresetKey, "custom">) {
    const range = computePresetRange(key, today)
    onStartChange(range.start)
    onEndChange(range.end)
    setOpen(false)
  }

  function chooseCustom() {
    setPendingMode("custom")
  }

  function selectDay(iso: string) {
    setPendingMode("custom")
    if (!pickAnchor) {
      setPickAnchor(iso)
      setPendingStart(iso)
      setPendingEnd(null)
      return
    }
    if (iso < pickAnchor) {
      setPendingStart(iso)
      setPendingEnd(pickAnchor)
    } else {
      setPendingStart(pickAnchor)
      setPendingEnd(iso)
    }
    setPickAnchor(null)
  }

  function goToPrevMonth() {
    if (viewMonth === 0) {
      setViewYear((year) => year - 1)
      setViewMonth(11)
    } else {
      setViewMonth((month) => month - 1)
    }
  }

  function goToNextMonth() {
    if (viewMonth === 11) {
      setViewYear((year) => year + 1)
      setViewMonth(0)
    } else {
      setViewMonth((month) => month + 1)
    }
  }

  function applyCustomRange() {
    if (!pendingStart || !pendingEnd) return
    onStartChange(pendingStart)
    onEndChange(pendingEnd)
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        disabled={disabled}
        aria-label={label}
        aria-expanded={open}
        onClick={() => (open ? setOpen(false) : openPopover())}
        className={cn(
          "inline-flex h-9 items-center gap-2 rounded border border-stroke bg-canvas px-4 py-2 shadow-md",
          "text-sm font-normal text-fg transition-colors duration-150",
          disabled ? "cursor-not-allowed opacity-60" : "hover:border-stroke-strong",
          focusRing,
          className,
        )}
      >
        <RiCalendar2Line size={20} className="shrink-0 text-fg-muted" aria-hidden="true" />
        <span className="whitespace-nowrap">{triggerLabel}</span>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 flex overflow-hidden rounded border border-stroke bg-surface-1 shadow-md">
          <div className="flex w-40 flex-col gap-0.5 border-r border-stroke p-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.key}
                type="button"
                onClick={() => choosePreset(preset.key)}
                className={cn(
                  "flex items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm text-fg-body hover:bg-surface-2 hover:text-fg",
                  pendingMode === preset.key && "bg-surface-3 font-medium text-fg",
                )}
              >
                {preset.label}
                {pendingMode === preset.key && (
                  <RiCheckLine size={14} className="shrink-0 text-fg" aria-hidden="true" />
                )}
              </button>
            ))}

            <div className="my-1 border-t border-stroke" />

            <button
              type="button"
              onClick={chooseCustom}
              className={cn(
                "flex items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm text-fg-body hover:bg-surface-2 hover:text-fg",
                pendingMode === "custom" && "bg-surface-3 font-medium text-fg",
              )}
            >
              Custom range
              {pendingMode === "custom" && (
                <RiCheckLine size={14} className="shrink-0 text-fg" aria-hidden="true" />
              )}
            </button>
          </div>

          <div className="flex flex-col">
            <DateRangeCalendar
              viewYear={viewYear}
              viewMonth={viewMonth}
              rangeStart={pendingStart}
              rangeEnd={pendingEnd}
              today={today}
              onSelectDay={selectDay}
              onPrevMonth={goToPrevMonth}
              onNextMonth={goToNextMonth}
            />
            <div className="flex items-center justify-between gap-2 border-t border-stroke px-4 py-3">
              <span className="text-xs text-fg-muted">
                {pendingStart && pendingEnd
                  ? formatRangeLabel(pendingStart, pendingEnd)
                  : "Pick a start date"}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded-md border border-stroke px-3 py-1.5 text-xs font-medium text-fg-body hover:border-stroke-strong"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={applyCustomRange}
                  disabled={!(pendingStart && pendingEnd)}
                  className="rounded-md bg-fg px-3 py-1.5 text-xs font-medium text-fg-on-primary hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Apply
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
