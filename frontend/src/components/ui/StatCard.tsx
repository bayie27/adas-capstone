import type { ElementType, ReactNode } from "react"
import { RiInformationLine } from "@remixicon/react"

import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { DeltaIndicator } from "@/components/ui/DeltaIndicator"
import { Tooltip } from "@/components/ui/Tooltip"

/**
 * The KPI card as drawn on `37:74` and `38:82`: an icon tile at --radius-lg
 * over a tracked uppercase caption, the value, and an optional subtext.
 *
 * Two variants the frames show and the old component could not express:
 *
 * - `elevated` — the highlighted first card in a KPI row, filled with
 *   --color-surface-2 (§2.2).
 * - `delta` — the "+12.5% compared to last month" indicator, a neutral
 *   boxed chip (see `DeltaIndicator`) rather than bare coloured text.
 *
 * §2.8's loading treatment for a KPI value is the single character `…`; pass
 * `isLoading` rather than threading that string through every call site.
 */
interface StatCardProps {
  icon: ElementType
  title: string
  value: ReactNode
  /** Optional subtext below the value. Accepts a string or any ReactNode
   * (e.g. a BadgeDot + label row for live status indicators). */
  subtext?: ReactNode
  delta?: string
  /** `true`/`false` pick the success/danger tone. `null` is a distinct third
   * state -- a real, present delta that is exactly zero -- rendered neutral
   * rather than defaulting to danger the way `false` would. */
  deltaPositive?: boolean | null
  elevated?: boolean
  isLoading?: boolean
  className?: string
  /** Optional tooltip content explaining what the metric means. */
  tooltip?: ReactNode
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
  tooltip,
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
        <div className="mb-2 flex min-h-[32px] items-center gap-1.5">
          <h4 className="text-xs font-medium uppercase tracking-wider text-fg-muted">{title}</h4>
          {tooltip ? (
            <Tooltip content={tooltip}>
              <button
                type="button"
                aria-label={`About ${title}`}
                className={cn(
                  "inline-flex items-center justify-center rounded-sm text-fg-muted transition-colors hover:text-fg",
                  focusRing,
                )}
              >
                <RiInformationLine size={14} aria-hidden="true" />
              </button>
            </Tooltip>
          ) : null}
        </div>
        <div className="flex items-center justify-between gap-2.5">
          <div className="text-3xl font-semibold leading-none tracking-tight text-fg">
            {isLoading ? "…" : value}
          </div>
          {delta ? (
            // Undefined (no explicit sign passed) reads as danger, same as
            // `false` -- `null` is the only value that means neutral.
            <DeltaIndicator
              value={delta}
              tone={deltaPositive === undefined ? false : deltaPositive}
            />
          ) : null}
        </div>
      </div>
      {subtext ? <div className="mt-4 text-xs text-fg-muted">{subtext}</div> : null}
    </Card>
  )
}
