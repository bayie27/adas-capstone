import { RiArrowRightDownLine, RiArrowRightLine, RiArrowRightUpLine } from "@remixicon/react"

import { cn } from "@/utils/cn"

/**
 * The trend chip on a KPI card ("+12.5%" next to a StatCard's value): a
 * neutral-bordered box, not a tinted pill -- Figma's boxed-chip frame keeps
 * the background and border plain and puts all the colour on the icon and
 * text.
 *
 * The arrow direction reflects the sign of `value` itself (did the raw
 * number go up or down), which is independent of `tone` (whether that
 * direction is good or bad news for this particular metric -- see
 * `deltaTone()` in Dashboard.tsx). A camera-count-style KPI where more is
 * worse still points its arrow up on a positive delta; only the colour
 * flips to danger.
 */
const TONE_TEXT: Record<"success" | "danger" | "neutral", string> = {
  success: "text-success",
  danger: "text-danger",
  neutral: "text-fg-muted",
}

function deltaDirection(value: string): "up" | "down" | "flat" {
  const trimmed = value.trim()
  if (trimmed.startsWith("+")) return "up"
  if (trimmed.startsWith("-") || trimmed.startsWith("−")) return "down"
  return "flat"
}

export function DeltaIndicator({
  value,
  tone,
  className,
}: {
  /** The formatted delta text, e.g. "+12.5%", "−1.2%", "0%". */
  value: string
  /** `true`/`false` picks success/danger; `null` is the neutral third
   * state -- a real, present delta that is exactly zero. */
  tone: boolean | null
  className?: string
}) {
  const resolvedTone = tone === null ? "neutral" : tone ? "success" : "danger"
  const direction = deltaDirection(value)
  const Arrow =
    direction === "up"
      ? RiArrowRightUpLine
      : direction === "down"
        ? RiArrowRightDownLine
        : RiArrowRightLine

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border border-stroke bg-surface-1 px-2 py-0.5 text-caption font-semibold",
        TONE_TEXT[resolvedTone],
        className,
      )}
    >
      <Arrow size={14} aria-hidden="true" data-testid={`delta-arrow-${direction}`} />
      {value}
    </span>
  )
}
