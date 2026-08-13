import type { ReactNode } from "react"

import { cn } from "@/utils/cn"

/**
 * The `Badge Primary` component from the Figma frames, in the three shapes
 * the screens actually draw:
 *
 * - `solid`   the status badge on the accident modals (ONGOING / RESOLVED),
 *             a filled pill with --color-fg-on-primary text.
 * - `subtle`  the tinted pill: the Online/Offline status dot on System Health
 *             and the delta indicators on the KPI cards, using the
 *             `-subtle` / `-border` token pairs from §2.2.
 * - `outline` a neutral chip with only a border.
 *
 * Geometry is §2.3: py-0.5 / px-2.5, and §2.4's uppercase-tracked caption
 * treatment for badge text.
 */
export type BadgeTone = "neutral" | "success" | "warning" | "danger"
export type BadgeVariant = "solid" | "subtle" | "outline"

const SOLID: Record<BadgeTone, string> = {
  neutral: "bg-surface-3 text-fg",
  success: "bg-success text-fg-on-primary",
  warning: "bg-warning text-fg-on-primary",
  danger: "bg-danger text-fg-on-primary",
}

const SUBTLE: Record<BadgeTone, string> = {
  neutral: "bg-surface-3 text-fg-muted border border-stroke",
  success: "bg-success-subtle text-success border border-success-border",
  warning: "bg-warning-subtle text-warning border border-warning-border",
  danger: "bg-danger-subtle text-danger border border-danger-border",
}

const OUTLINE: Record<BadgeTone, string> = {
  neutral: "border border-stroke text-fg-muted",
  success: "border border-success-border text-success",
  warning: "border border-warning-border text-warning",
  danger: "border border-danger-border text-danger",
}

const VARIANTS: Record<BadgeVariant, Record<BadgeTone, string>> = {
  solid: SOLID,
  subtle: SUBTLE,
  outline: OUTLINE,
}

export function Badge({
  tone = "neutral",
  variant = "solid",
  uppercase = true,
  icon,
  className,
  children,
}: {
  tone?: BadgeTone
  variant?: BadgeVariant
  /** §2.4 — badge text is uppercase and tracked. Off for numeric deltas. */
  uppercase?: boolean
  /** Leading mark, e.g. the filled dot on the Online pill. */
  icon?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-caption font-medium",
        uppercase && "uppercase tracking-[0.08em]",
        VARIANTS[variant][tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}

/** The filled dot the Figma Online/Offline pill carries. */
export function BadgeDot({ tone = "neutral" }: { tone?: BadgeTone }) {
  const fill: Record<BadgeTone, string> = {
    neutral: "bg-fg-muted",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
  }
  return <span className={cn("h-2 w-2 rounded-full", fill[tone])} aria-hidden="true" />
}
