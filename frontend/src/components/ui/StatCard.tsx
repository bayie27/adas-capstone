import type { ElementType, ReactNode } from "react"

import { cn } from "@/utils/cn"
import { Badge } from "@/components/ui/Badge"
import { Card } from "@/components/ui/Card"

/**
 * The KPI card as drawn on `37:74` and `38:82`: an icon tile at --radius-lg
 * over a tracked uppercase caption, the value, and an optional subtext.
 *
 * Two variants the frames show and the old component could not express:
 *
 * - `elevated` — the highlighted first card in a KPI row, filled with
 *   --color-surface-2 (§2.2).
 * - `delta` — the "+12.5% compared to last month" indicator, which Figma
 *   draws as a tinted pill, so it is a Badge on the subtle triplet rather
 *   than bare coloured text.
 *
 * §2.8's loading treatment for a KPI value is the single character `…`; pass
 * `isLoading` rather than threading that string through every call site.
 */
interface StatCardProps {
  icon: ElementType
  title: string
  value: ReactNode
  subtext?: string
  delta?: string
  /** `true`/`false` pick the success/danger tone. `null` is a distinct third
   * state -- a real, present delta that is exactly zero -- rendered neutral
   * rather than defaulting to danger the way `false` would. */
  deltaPositive?: boolean | null
  elevated?: boolean
  isLoading?: boolean
  className?: string
}

export function StatCard({
  icon: Icon,
  title,
  value,
  subtext,
  delta,
  deltaPositive,
  elevated = false,
  isLoading = false,
  className,
}: StatCardProps) {
  return (
    <Card
      elevated={elevated}
      className={cn("flex h-full min-h-[160px] flex-col justify-between", className)}
    >
      <div>
        <div
          className={cn(
            "mb-4 flex h-9 w-9 items-center justify-center rounded-lg border border-stroke",
            elevated ? "bg-surface-3" : "bg-surface-2",
          )}
        >
          <Icon size={17} className="text-fg-muted" />
        </div>
        <h4 className="mb-2 min-h-[32px] text-[11px] font-medium uppercase tracking-wider text-fg-muted">
          {title}
        </h4>
        <div className="flex items-end gap-2.5">
          <div className="text-3xl font-semibold leading-none tracking-tight text-fg">
            {isLoading ? "…" : value}
          </div>
          {delta ? (
            <Badge
              variant="subtle"
              tone={deltaPositive === null ? "neutral" : deltaPositive ? "success" : "danger"}
              uppercase={false}
              className="mb-1"
            >
              {delta}
            </Badge>
          ) : null}
        </div>
      </div>
      {subtext ? <div className="mt-4 text-xs text-fg-muted">{subtext}</div> : null}
    </Card>
  )
}
