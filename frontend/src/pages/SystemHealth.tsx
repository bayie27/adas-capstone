import { useState, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { AreaChartCard, ChartMessage } from "@/components/charts/AreaChartCard"
import { AXIS_PROPS, CHART, TOOLTIP_PROPS } from "@/components/charts/chartTheme"
import { BadgeDot } from "@/components/ui/Badge"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { StatCard } from "@/components/ui/StatCard"
import { Tabs } from "@/components/ui/Tabs"
import { getSystemHealthHistory, getSystemHealthLive } from "@/api/health"
import type { SystemHealthDataPoint, SystemHealthLiveResponse } from "@/api/health"
import { getOperatorWarningEntry } from "@/utils/warningCopy"
import { formatRelativeDateTime } from "@/utils/datetime"
import { cn } from "@/utils/cn"
import {
  RiAlertLine,
  RiCheckboxCircleLine,
  RiDashboard3Line,
  RiHardDrive2Line,
  RiServerLine,
  RiTimerLine,
} from "@remixicon/react"

// ─── helpers ────────────────────────────────────────────────────────────────

function formatUptime(seconds: number | null | undefined): string {
  // Nullable like every other measurement: the collector reports null until
  // its first sample completes.
  if (seconds == null) return "N/A"
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${d}d ${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`
}

const BYTES_PER_GB = 1024 ** 3

function formatDiskSubtext(live: SystemHealthLiveResponse | undefined): string | undefined {
  if (!live) return undefined
  // `disk_available: false` is a legitimate backend state — that sensor
  // failed on an otherwise-good sample — so it gets a message rather than
  // a number, and never a crash.
  if (!live.disk_available) return "Disk metrics unavailable"
  const { disk_available_bytes: free, disk_total_bytes: total } = live
  if (free == null || total == null) return undefined
  return `${(free / BYTES_PER_GB).toFixed(1)} GB free of ${(total / BYTES_PER_GB).toFixed(1)} GB`
}

function formatServerUptimeSubtext(live: SystemHealthLiveResponse | undefined): string | undefined {
  if (!live || live.process_uptime_seconds == null) return undefined
  return `Backend process: ${formatUptime(live.process_uptime_seconds)}`
}

// avg_fps and avg_inference_latency_ms are aggregated across whatever
// cameras reported freshly — "12.4 FPS" doesn't say whether that's one
// camera or forty, and those are different facts. This is their
// denominator, so it belongs as the subtext on those two cards rather than
// a card of its own.
function formatSampleCameraSubtext(live: SystemHealthLiveResponse | undefined): string | undefined {
  if (!live) return undefined
  const count = live.sample_camera_count
  return count === 1 ? "1 camera reporting" : `${count} cameras reporting`
}

function formatPercent(value: number | null | undefined): string {
  if (value == null) return "N/A"
  return `${value.toFixed(1)}%`
}

function formatMs(value: number | null | undefined): string {
  if (value == null) return "N/A"
  return `${value.toFixed(0)}ms`
}

function formatFps(value: number | null | undefined): string {
  if (value == null) return "N/A"
  return `${value.toFixed(1)} fps`
}

/**
 * Three distinct states the backend reports and nothing distinguished
 * before this: `collected_at: null` (the collector hasn't finished its
 * first sample — not an error, the page has only just started), `stale:
 * true` (the collector is behind its interval — the numbers below are old),
 * and neither (a normal, current sample). Collapsing these to one dash was
 * the same failure class that took this page down before PR #83: an
 * operator cannot tell "nothing to show yet" from "this is wrong" from
 * "this is fine but a minute old."
 */
function formatSampleStatus(live: SystemHealthLiveResponse | undefined): ReactNode {
  if (!live) return null
  if (live.collected_at === null) {
    return (
      <div className="text-right">
        <div className="text-[12px] text-fg-muted">Data refreshed</div>
        <div className="text-[14px] font-medium text-fg-muted">Collecting sample…</div>
      </div>
    )
  }
  if (live.stale) {
    return (
      <div className="text-right">
        <div className="text-[12px] text-warning">Data refreshed</div>
        <div className="text-[14px] font-medium text-warning">
          {formatRelativeDateTime(live.collected_at)}
        </div>
      </div>
    )
  }
  return (
    <div className="text-right">
      <div className="text-[12px] text-fg-muted">Data refreshed</div>
      <div className="text-[14px] font-medium text-fg">Just now</div>
    </div>
  )
}

/**
 * The live counterpart to a history chart, in the chart header's `action`
 * slot. `*_available: false` is a legitimate state — that sensor failed on
 * an otherwise-good sample, distinct from a null value on a working sensor
 * (which can't happen here — nullability and the flag move together) and
 * distinct from no sample having been collected at all yet.
 */
function LiveReading({
  value,
  available,
  unit,
}: {
  value: number | null
  available: boolean
  unit: string
}) {
  if (!available) {
    return <span className="text-caption text-fg-muted">Live: unavailable</span>
  }
  return (
    <span className="text-caption text-fg-muted">
      Live: {value !== null ? `${value.toFixed(1)}${unit}` : "N/A"}
    </span>
  )
}

function formatTimestamp(value: string, range: "48h" | "30d"): string {
  const date = new Date(value)
  if (range === "30d") {
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
  }
  return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })
}

function toChartData(
  data: SystemHealthDataPoint[],
  dataKey: keyof SystemHealthDataPoint,
  range: "48h" | "30d",
) {
  return data.map((point) => ({
    time: formatTimestamp(point.timestamp, range),
    value: point[dataKey] as number | null,
  }))
}

const RANGE_TABS = [
  { value: "48h" as const, label: "Last 48 Hours" },
  { value: "30d" as const, label: "30-Day Trend" },
]

// ─── Operational Banner ──────────────────────────────────────────────────────

/**
 * Top-level status banner for DRRMO operators and the Head of Operations.
 *
 * Three mutually exclusive states (evaluated in priority order):
 *   1. Stale / no sample — amber, "data may be out of date"
 *   2. Active warnings — highest-severity warning headlined, "+N more" expander
 *   3. All clear — green, fps + camera count context
 *
 * Warning copy is sourced exclusively from warningCopy.ts — never inlined here.
 */
function OperationalBanner({ live }: { live: SystemHealthLiveResponse | undefined }) {
  const [warningsExpanded, setWarningsExpanded] = useState(false)

  // ── State 1: stale or no sample yet ──────────────────────────────────────
  const isStale = !live || live.collected_at === null || live.stale
  if (isStale) {
    return (
      <div className="mb-6 flex items-center gap-3 rounded-xl border border-warning-border bg-warning-subtle px-5 py-4">
        <RiAlertLine size={18} className="shrink-0 text-warning" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium text-warning">
            System data may be slightly out of date
          </p>
          <p className="mt-0.5 text-xs text-warning opacity-80">
            Recent changes may not be visible yet. The dashboard refreshes automatically.
          </p>
        </div>
      </div>
    )
  }

  const warnings = live.warnings ?? []

  // ── State 2: active warnings ──────────────────────────────────────────────
  if (warnings.length > 0) {
    // Sort: critical first, then warning — server may already do this but
    // we enforce it here for display safety.
    const sorted = [...warnings].sort((a, b) => {
      if (a.severity === b.severity) return 0
      return a.severity === "critical" ? -1 : 1
    })
    const primary = sorted[0]
    const rest = sorted.slice(1)
    const primaryEntry = getOperatorWarningEntry(primary)
    const isBad = primaryEntry.tone === "bad"

    return (
      <div
        className={cn(
          "mb-6 rounded-xl border px-5 py-4",
          isBad
            ? "border-danger-border bg-danger-subtle"
            : "border-warning-border bg-warning-subtle",
        )}
      >
        <div className="flex items-center gap-3">
          <RiAlertLine
            size={18}
            className={cn("shrink-0", isBad ? "text-danger" : "text-warning")}
            aria-hidden="true"
          />
          <div className="flex-1 min-w-0">
            <p className={cn("text-sm font-medium", isBad ? "text-danger" : "text-warning")}>
              {primaryEntry.text}
            </p>
            <p className={cn("mt-0.5 text-xs opacity-80", isBad ? "text-danger" : "text-warning")}>
              {primaryEntry.detail}
            </p>

            {rest.length > 0 && (
              <div className="mt-3">
                <button
                  type="button"
                  onClick={() => setWarningsExpanded((v) => !v)}
                  className={cn(
                    "text-xs font-medium underline-offset-2 hover:underline focus:outline-none",
                    isBad ? "text-danger" : "text-warning",
                  )}
                >
                  {warningsExpanded
                    ? "Show less"
                    : `+${rest.length} more issue${rest.length > 1 ? "s" : ""}`}
                </button>

                {warningsExpanded && (
                  <ul className="mt-2 flex flex-col gap-1.5">
                    {rest.map((w, i) => {
                      const entry = getOperatorWarningEntry(w)
                      return (
                        <li
                          key={`${w.code}-${i}`}
                          className={cn(
                            "text-xs opacity-90",
                            entry.tone === "bad" ? "text-danger" : "text-warning",
                          )}
                        >
                          <span className="font-medium">{entry.text}</span>
                          {" — "}
                          {entry.detail}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ── State 3: all clear ────────────────────────────────────────────────────
  const fpsText = live.avg_fps != null ? `Processing at ${live.avg_fps.toFixed(1)} fps` : null
  const cameraText =
    live.sample_camera_count === 0
      ? "No cameras currently reporting"
      : live.sample_camera_count === 1
        ? "1 camera currently reporting"
        : `${live.sample_camera_count} cameras currently reporting`

  const contextParts = [fpsText, cameraText].filter(Boolean).join(" · ")

  return (
    <div className="mb-6 flex items-center gap-3 rounded-xl border border-success-border bg-success-subtle px-5 py-4">
      <RiCheckboxCircleLine size={18} className="shrink-0 text-success" aria-hidden="true" />
      <div>
        <p className="text-sm font-medium text-success">All systems normal</p>
        {contextParts && <p className="mt-0.5 text-xs text-success opacity-80">{contextParts}</p>}
      </div>
    </div>
  )
}

// ─── KPI card helpers ────────────────────────────────────────────────────────

/**
 * Disk storage dot — tone driven by presence of DISK_CRITICAL / DISK_WARNING
 * in live.warnings (matching the thresholds the backend already evaluates)
 * rather than duplicating threshold constants in the frontend.
 */
function diskDotTone(live: SystemHealthLiveResponse | undefined): "success" | "warning" | "danger" {
  if (!live) return "success"
  const codes = (live.warnings ?? []).map((w) => w.code)
  if (codes.includes("DISK_CRITICAL")) return "danger"
  if (codes.includes("DISK_WARNING")) return "warning"
  return "success"
}

/**
 * The history points carry avg/peak *pairs* for two metrics — cpu_temp and
 * gpu_mem_pct — that nothing plotted at all before this, on top of the four
 * single-series charts Figma draws. AreaChartCard is a single-series
 * primitive, and adding a second dataKey to it would change it for every
 * page that already uses it (Dashboard, AI Performance's siblings); this is
 * a page-local dual-line chart instead, built on the same chartTheme tokens
 * and the same loading/empty states rather than a third styling system.
 * Peak is the solid line — it's the number that matters for a threshold
 * breach — and avg is the same colour at reduced opacity, dashed, rather
 * than a second arbitrary colour.
 */
function DualHealthChart({
  title,
  data,
  avgKey,
  peakKey,
  unit,
  isLoading,
  action,
}: {
  title: string
  data: SystemHealthDataPoint[]
  avgKey: keyof SystemHealthDataPoint
  peakKey: keyof SystemHealthDataPoint
  unit: string
  isLoading: boolean
  action?: ReactNode
}) {
  const chartData = data.map((point) => ({
    time: point.timestamp,
    avg: point[avgKey] as number | null,
    peak: point[peakKey] as number | null,
  }))
  const isEmpty = !isLoading && chartData.length === 0
  // The history endpoint returns one row per time bucket regardless of
  // whether the sensor behind avgKey/peakKey ever reports -- cpu_temp is
  // null in every row on a host with no readable CPU sensor (Windows, per
  // the comment above this component's only two call sites), so
  // `chartData.length === 0` never fires and this used to fall through to
  // a real <AreaChart> with nothing to plot: axes and a legend around a
  // blank rectangle. Distinct from `isEmpty` (a real "no rows for this
  // range" gap) because the fix is different -- MachineCapacitySection's
  // "Unavailable" shell, not AreaChartCard's "No data for this range."
  const isUnavailable =
    !isLoading &&
    chartData.length > 0 &&
    chartData.every((point) => point.avg === null && point.peak === null)

  return (
    <div
      className="flex flex-col rounded-xl border border-stroke bg-surface-1 p-5 shadow-sm"
      style={{ height: 260 }}
    >
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h3 className="text-caption font-medium text-fg-body">{title}</h3>
          <span className="flex items-center gap-1 text-[10px] text-fg-muted">
            <span className="inline-block h-0.5 w-3 bg-[var(--color-chart-line)]" /> Peak
          </span>
          <span className="flex items-center gap-1 text-[10px] text-fg-muted">
            <span className="inline-block h-0.5 w-3 bg-[var(--color-chart-line)] opacity-40" /> Avg
          </span>
        </div>
        {action}
      </div>

      {isLoading ? (
        <ChartMessage>…</ChartMessage>
      ) : isEmpty ? (
        <ChartMessage>No data for this range.</ChartMessage>
      ) : isUnavailable ? (
        <ChartMessage>Unavailable — not reported on this host.</ChartMessage>
      ) : (
        <div className="-ml-4 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="time" {...AXIS_PROPS} dy={8} tick={false} />
              <YAxis {...AXIS_PROPS} width={32} tickFormatter={(v) => `${v}${unit}`} />
              <Tooltip
                {...TOOLTIP_PROPS}
                cursor={{ stroke: "var(--color-stroke-strong)", strokeWidth: 1 }}
                formatter={(value, name) => [
                  value === null ? "N/A" : `${Number(value).toFixed(1)}${unit}`,
                  name === "peak" ? "Peak" : "Avg",
                ]}
              />
              <Area
                type="monotone"
                dataKey="peak"
                stroke={CHART.line}
                strokeWidth={1.5}
                fill="none"
                dot={false}
              />
              <Area
                type="monotone"
                dataKey="avg"
                stroke={CHART.line}
                strokeOpacity={0.4}
                strokeDasharray="4 3"
                strokeWidth={1.5}
                fill="none"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function SystemHealth() {
  const [activeTab, setActiveTab] = useState<"48h" | "30d">("48h")

  const liveQuery = useQuery({
    queryKey: ["system-health-live"],
    queryFn: getSystemHealthLive,
    refetchInterval: (query) =>
      // Stop polling if the endpoint doesn't exist yet (404/500)
      query.state.error ? false : 15_000,
    retry: 1,
  })

  const historyQuery = useQuery({
    queryKey: ["system-health-history", activeTab],
    queryFn: () => getSystemHealthHistory(activeTab),
    retry: 1,
  })

  const live = liveQuery.data
  const historyData = historyQuery.data?.points ?? []

  // Disk dot tone — derived from warning presence, not hardcoded thresholds
  const diskTone = diskDotTone(live)

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      {/* ── Page header ────────────────────────────────────────────────── */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="mb-0.5 text-xl font-semibold text-fg">System Health</h1>
          <p className="text-xs text-fg-muted">
            Oversee system diagnostics and hardware performance
          </p>
        </div>
        <div>{formatSampleStatus(live)}</div>
      </div>

      {/* ── Live query error ────────────────────────────────────────────── */}
      {liveQuery.isError ? (
        <QueryErrorBanner
          error={liveQuery.error}
          fallback="Live health metrics unavailable."
          onRetry={() => liveQuery.refetch()}
        />
      ) : null}

      {/* ── Operational status banner ───────────────────────────────────── */}
      {!liveQuery.isError && <OperationalBanner live={live} />}

      {/* ── KPI stat cards ─────────────────────────────────────────────── */}
      <div className="mb-8 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={RiServerLine}
          title="Server Uptime"
          value={formatUptime(live?.host_uptime_seconds)}
          isLoading={liveQuery.isLoading}
          subtext={formatServerUptimeSubtext(live)}
        />
        <StatCard
          icon={RiTimerLine}
          title="Inference Latency"
          value={
            live ? (
              <span className="inline-flex items-center gap-[14px]">
                {formatMs(live.avg_inference_latency_ms)}
                <BadgeDot tone={live.sample_camera_count > 0 ? "success" : "danger"} />
              </span>
            ) : (
              formatMs(undefined)
            )
          }
          isLoading={liveQuery.isLoading}
          subtext={formatSampleCameraSubtext(live)}
        />
        <StatCard
          icon={RiDashboard3Line}
          title="Processing Speed"
          value={
            live ? (
              <span className="inline-flex items-center gap-[14px]">
                {formatFps(live.avg_fps)}
                <BadgeDot tone={live.sample_camera_count > 0 ? "success" : "danger"} />
              </span>
            ) : (
              formatFps(undefined)
            )
          }
          isLoading={liveQuery.isLoading}
          subtext={formatSampleCameraSubtext(live)}
        />
        <StatCard
          icon={RiHardDrive2Line}
          title="Disk Storage Usage"
          value={
            live ? (
              <span className="inline-flex items-center gap-[14px]">
                {formatPercent(live.disk_percent)}
                <BadgeDot tone={diskTone} />
              </span>
            ) : (
              formatPercent(undefined)
            )
          }
          isLoading={liveQuery.isLoading}
          subtext={formatDiskSubtext(live)}
        />
      </div>

      {/* ── History range tabs + 6 charts ──────────────────────────────── */}
      <div className="mb-5">
        <Tabs
          items={RANGE_TABS}
          value={activeTab}
          onChange={setActiveTab}
          variant="pill"
          label="History range"
        />
      </div>

      {historyQuery.isError ? (
        <QueryErrorBanner
          error={historyQuery.error}
          fallback="Historical health data unavailable."
          onRetry={() => historyQuery.refetch()}
        />
      ) : null}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <AreaChartCard
          title="CPU Utilization"
          data={toChartData(historyData, "cpu_usage", activeTab)}
          dataKey="value"
          xKey="time"
          height={260}
          isLoading={historyQuery.isLoading}
          allowDecimals={false}
          yDomain={[0, 100]}
          unit="%"
          tooltipFormatter={(v) => [`${Number(v).toFixed(1)}%`, "CPU Utilization"]}
          action={
            live ? (
              <LiveReading value={live.cpu_usage} available={live.cpu_usage_available} unit="%" />
            ) : null
          }
        />
        <AreaChartCard
          title="GPU Utilization"
          data={toChartData(historyData, "gpu_usage", activeTab)}
          dataKey="value"
          xKey="time"
          height={260}
          isLoading={historyQuery.isLoading}
          allowDecimals={false}
          yDomain={[0, 100]}
          unit="%"
          tooltipFormatter={(v) => [`${Number(v).toFixed(1)}%`, "GPU Utilization"]}
        />
        {/*
          Figma's fourth chart is "Core Temperature". The history points carry
          cpu_temp_avg/peak and gpu_temp_peak — all null on Windows for CPU.
          Wired to gpu_temp_peak and labelled GPU Temperature; recorded as a
          design/backend mismatch rather than silently relabelled.
        */}
        <AreaChartCard
          title="GPU Temperature"
          data={toChartData(historyData, "gpu_temp_peak", activeTab)}
          dataKey="value"
          xKey="time"
          height={260}
          isLoading={historyQuery.isLoading}
          allowDecimals={false}
          unit="°C"
          stroke={CHART.danger}
          tooltipFormatter={(v) => [`${Number(v).toFixed(1)}°C`, "GPU Temperature"]}
        />
        <AreaChartCard
          title="RAM Utilization"
          data={toChartData(historyData, "ram_usage", activeTab)}
          dataKey="value"
          xKey="time"
          height={260}
          isLoading={historyQuery.isLoading}
          allowDecimals={false}
          yDomain={[0, 100]}
          unit="%"
          tooltipFormatter={(v) => [`${Number(v).toFixed(1)}%`, "RAM Utilization"]}
          action={
            live ? (
              <LiveReading value={live.ram_usage} available={live.ram_usage_available} unit="%" />
            ) : null
          }
        />
        {/*
          cpu_temp_avg/peak — null on Windows for CPU, per the plan's own
          note — and gpu_mem_pct_avg/peak were both carried by the history
          endpoint and plotted nowhere. Two more chart cards than Figma
          draws; no frame for these, so genuinely unavailable (Windows CPU
          temp) renders as an honest gap rather than a fabricated flat line.
        */}
        <DualHealthChart
          title="CPU Temperature"
          data={historyData}
          avgKey="cpu_temp_avg"
          peakKey="cpu_temp_peak"
          unit="°C"
          isLoading={historyQuery.isLoading}
          action={
            live ? (
              <LiveReading value={live.cpu_temp} available={live.cpu_temp_available} unit="°C" />
            ) : null
          }
        />
        <DualHealthChart
          title="GPU Memory"
          data={historyData}
          avgKey="gpu_mem_pct_avg"
          peakKey="gpu_mem_pct_peak"
          unit="%"
          isLoading={historyQuery.isLoading}
        />
      </div>
    </div>
  )
}
