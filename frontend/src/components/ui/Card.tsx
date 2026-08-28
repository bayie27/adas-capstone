import type { ReactNode } from "react"

import { cn } from "@/utils/cn"

/**
 * The card container the frames wrap every panel in: --color-surface-1 on a
 * --color-stroke border at --radius-xl with --shadow-sm (§2.2, §2.5, §2.6).
 *
 * `elevated` is the highlighted first KPI card on Cameras and the Dashboard,
 * which Figma fills with --color-surface-2 (§2.2).
 */
export function Card({
  elevated = false,
  padded = true,
  className,
  children,
}: {
  elevated?: boolean
  /** Off for cards whose content owns its own padding, e.g. a table. */
  padded?: boolean
  className?: string
  children: ReactNode
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-stroke shadow-sm",
        elevated ? "bg-surface-2" : "bg-surface-1",
        padded && "p-5",
        className,
      )}
    >
      {children}
    </div>
  )
}

/** Card title row — §2.4's p-medium, with an optional right-aligned slot. */
export function CardHeader({
  title,
  action,
  className,
}: {
  title: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn("mb-4 flex items-center justify-between gap-4", className)}>
      <h3 className="text-secondary font-medium text-fg">{title}</h3>
      {action}
    </div>
  )
}
