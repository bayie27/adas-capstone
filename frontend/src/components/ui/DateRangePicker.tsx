import { useId } from "react"
import { RiCalendarLine } from "@remixicon/react"

import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

/**
 * One range control, which is what Figma draws ("March 11, 2026 - March 14,
 * 2026") — not two fields with a "to" between them, which is what Dashboard,
 * Detections and AI Performance currently hand-roll three times each.
 *
 * Both halves are native `<input type="date">`. That keeps the platform date
 * picker, its keyboard handling and its locale formatting rather than
 * reimplementing a calendar, and `[color-scheme:dark]` is what makes the
 * native picker render dark instead of a white sheet on a dark console.
 *
 * States per §2.8: the shared focus-visible ring on each half, hover lifting
 * the container border to --color-stroke-strong, and disabled at opacity-60.
 * `min`/`max` clamp the two halves against each other so the range cannot be
 * inverted in the first place.
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
  const id = useId()
  const fieldClass = cn(
    "bg-transparent text-xs font-normal text-fg [color-scheme:dark] focus:outline-none",
    "disabled:cursor-not-allowed",
    focusRing,
  )

  return (
    <div
      role="group"
      aria-label={label}
      className={cn(
        "inline-flex h-9 items-center gap-2 rounded border border-stroke bg-canvas px-4 py-2 shadow-md",
        "transition-colors duration-150 text-xs font-normal text-fg",
        disabled ? "cursor-not-allowed opacity-60" : "hover:border-stroke-strong",
        className,
      )}
    >
      <RiCalendarLine size={16} className="shrink-0 text-fg" aria-hidden="true" />
      <input
        id={`${id}-start`}
        type="date"
        value={start}
        max={end || undefined}
        disabled={disabled}
        onChange={(event) => onStartChange(event.target.value)}
        aria-label={`${label} start`}
        className={fieldClass}
      />
      <span aria-hidden="true" className="text-xs font-normal text-fg">
        –
      </span>
      <input
        id={`${id}-end`}
        type="date"
        value={end}
        min={start || undefined}
        disabled={disabled}
        onChange={(event) => onEndChange(event.target.value)}
        aria-label={`${label} end`}
        className={fieldClass}
      />
    </div>
  )
}
