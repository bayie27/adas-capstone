import { useId, type ComponentProps, type ReactNode } from "react"
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { cn } from "@/utils/cn"
import { AXIS_PROPS, CHART, TOOLTIP_PROPS } from "@/components/charts/chartTheme"
import { ChartMessage } from "@/components/charts/AreaChartCard"

/**
 * The `Accident Frequency by Location` chart: horizontal bars on a greyscale
 * ramp keyed to magnitude.
 *
 * §2.2 keeps that ramp as a computed `hsl()` rather than a token, because it
 * is data-driven — the lightness encodes the value — and a palette entry
 * cannot express that. The formula is the spec: `L = 30 + 45 x (value / max)`,
 * fading horizontally to `max(L - 15, 15)`. It is the one place in the app
 * where a colour is computed, and it lives here rather than inline in a page.
 */
function rampLightness(value: number, max: number) {
  return max > 0 ? 30 + 45 * (value / max) : 30
}

export function BarChartCard({
  title,
  data,
  dataKey,
  labelKey,
  height = 270,
  isLoading = false,
  error,
  emptyMessage = "No data for this range.",
  tooltipFormatter,
  action,
  className,
}: {
  title: ReactNode
  data: Array<Record<string, unknown>>
  /** Numeric field driving both bar length and ramp lightness. */
  dataKey: string
  /** Category field on the Y axis. */
  labelKey: string
  height?: number
  isLoading?: boolean
  error?: string
  emptyMessage?: string
  tooltipFormatter?: ComponentProps<typeof Tooltip>["formatter"]
  action?: ReactNode
  className?: string
}) {
  const gradientPrefix = useId().replace(/:/g, "")
  const isEmpty = !isLoading && !error && data.length === 0
  const max = data.reduce((acc, row) => Math.max(acc, Number(row[dataKey]) || 0), 0)

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
            <BarChart data={data} layout="vertical" barCategoryGap={8}>
              <defs>
                {data.map((row, index) => {
                  const lightness = rampLightness(Number(row[dataKey]) || 0, max)
                  return (
                    <linearGradient
                      key={index}
                      id={`${gradientPrefix}-${index}`}
                      x1="0"
                      y1="0"
                      x2="1"
                      y2="0"
                    >
                      <stop offset="0%" stopColor={`hsl(0,0%,${lightness}%)`} stopOpacity={1} />
                      <stop
                        offset="100%"
                        stopColor={`hsl(0,0%,${Math.max(lightness - 15, 15)}%)`}
                        stopOpacity={1}
                      />
                    </linearGradient>
                  )
                })}
              </defs>
              <XAxis type="number" {...AXIS_PROPS} hide />
              <YAxis
                type="category"
                dataKey={labelKey}
                {...AXIS_PROPS}
                width={140}
                tick={{ fill: CHART.axis, fontSize: 10 }}
              />
              <Tooltip
                {...TOOLTIP_PROPS}
                cursor={{ fill: CHART.line, fillOpacity: 0.03 }}
                formatter={tooltipFormatter}
              />
              <Bar dataKey={dataKey} radius={[0, 4, 4, 0]}>
                {data.map((_, index) => (
                  <Cell key={index} fill={`url(#${gradientPrefix}-${index})`} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
