/**
 * Every Recharts prop that carries a colour, in one place.
 *
 * A utility class cannot reach a Recharts prop, so the chart layer is the one
 * part of the app that consumes tokens as `var(--color-*)` (§2.1). Before
 * this, those 39 values were spread across two pages, which is exactly how
 * three of them drifted to different greys. The ESLint rule bans bare colour
 * literals; this is where the permitted `var()` forms live.
 */
export const CHART = {
  line: "var(--color-chart-line)",
  fillFrom: "var(--color-chart-fill-from)",
  fillTo: "var(--color-chart-fill-to)",
  grid: "var(--color-chart-grid)",
  axis: "var(--color-chart-axis)",
  danger: "var(--color-danger)",
} as const

/** Shared axis config — §2.2: axis lines and tick marks are hidden. */
export const AXIS_PROPS = {
  stroke: CHART.grid,
  tick: { fill: CHART.axis, fontSize: 11 },
  axisLine: false,
  tickLine: false,
} as const

/** Tooltip chrome: surface-1 card, stroke border, radius-md (§2.5). */
export const TOOLTIP_PROPS = {
  contentStyle: {
    backgroundColor: "var(--color-surface-1)",
    border: "1px solid var(--color-stroke)",
    borderRadius: "6px",
    fontSize: 12,
  },
  itemStyle: { color: "var(--color-fg-body)" },
  labelStyle: { color: "var(--color-fg-muted)" },
} as const
