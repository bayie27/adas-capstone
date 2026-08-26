import { useId, type ComponentProps, type ReactNode } from "react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { cn } from "@/utils/cn"
import { AXIS_PROPS, CHART, TOOLTIP_PROPS } from "@/components/charts/chartTheme"

/**
 * The area chart as every frame draws it: a white stroke over a vertical fade
 * to transparent, horizontal grid only, hidden axis lines (§2.2).
 *
 * Carries the three §2.8 body states a chart has — loading renders the `…`
 * treatment, empty renders a centred sentence, error renders the same centred
 * sentence in --color-danger — so no page re-implements them and none of them
 * gets forgotten.
 */
export function AreaChartCard({
  title,
  data,
  dataKey,
  xKey = "time",
  height = 270,
  unit,
  isLoading = false,
  error,
  emptyMessage = "No data for this range.",
  stroke = CHART.line,
  yDomain,
  allowDecimals = false,
  yWidth = 38,
  tooltipFormatter,
  tooltipLabelFormatter,
  action,
  className,
}: {
  title: ReactNode
  data: Array<Record<string, unknown>>
  dataKey: string
  xKey?: string
  height?: number
  unit?: string
  isLoading?: boolean
  error?: string
  emptyMessage?: string
  /** Defaults to the chart-line token; System Health's GPU temperature is danger. */
  stroke?: string
  yDomain?: [number, number]
  allowDecimals?: boolean
  yWidth?: number
  tooltipFormatter?: ComponentProps<typeof Tooltip>["formatter"]
  tooltipLabelFormatter?: ComponentProps<typeof Tooltip>["labelFormatter"]
  action?: ReactNode
  className?: string
}) {
  const gradientId = useId()
  const isEmpty = !isLoading && !error && data.length === 0

  return (
    <div
      className={cn(
        "flex flex-col rounded-xl border border-stroke bg-surface-1 p-5 shadow-sm",
        className,
      )}
      style={{ height }}
    >
      <div className="mb-4 flex items-center justify-between gap-4">
        <h3 className="text-caption font-medium text-fg-body">{title}</h3>
        {action}
      </div>

      {isLoading ? (
        <ChartMessage>…</ChartMessage>
      ) : error ? (
        <ChartMessage tone="danger">{error}</ChartMessage>
      ) : isEmpty ? (
        <ChartMessage>{emptyMessage}</ChartMessage>
      ) : (
        <div className="flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART.fillFrom} />
                  <stop offset="100%" stopColor={CHART.fillTo} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
              <XAxis dataKey={xKey} {...AXIS_PROPS} dy={8} />
              <YAxis
                {...AXIS_PROPS}
                allowDecimals={allowDecimals}
                domain={yDomain}
                width={yWidth}
                tickFormatter={unit ? (value) => `${value}${unit}` : undefined}
              />
              <Tooltip
                {...TOOLTIP_PROPS}
                cursor={{ stroke: "var(--color-stroke-strong)", strokeWidth: 1 }}
                formatter={tooltipFormatter}
                labelFormatter={tooltipLabelFormatter}
              />
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={stroke}
                strokeWidth={1.5}
                fill={`url(#${gradientId})`}
                dot={false}
                activeDot={{ r: 4, fill: stroke, stroke }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

export function ChartMessage({
  tone = "muted",
  children,
}: {
  tone?: "muted" | "danger"
  children: ReactNode
}) {
  return (
    <div
      className={cn(
        "flex flex-1 items-center justify-center text-center text-caption",
        tone === "danger" ? "text-danger" : "text-fg-muted",
      )}
    >
      {children}
    </div>
  )
}
