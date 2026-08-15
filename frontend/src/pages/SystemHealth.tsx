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
import { Badge } from "@/components/ui/Badge"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { StatCard } from "@/components/ui/StatCard"
import { Tabs } from "@/components/ui/Tabs"
import { getSystemHealth, getSystemHealthHistory, getSystemHealthLive } from "@/api/health"
import type {
  GpuRead,
  HealthWarning,
  SystemHealthDataPoint,
  SystemHealthLiveResponse,
} from "@/api/health"
import { describeWarning } from "@/utils/healthWarnings"
import { formatRelativeDateTime } from "@/utils/datetime"
import { truncateLabel } from "@/utils/format"
import { cn } from "@/utils/cn"
import {
  RiAlertLine,
  RiCpuLine,
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

function formatTemp(value: number | null | undefined): string {
  if (value == null) return "N/A"
  return `${value.toFixed(0)}°C`
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
    return <span className="text-fg-muted">Collecting the first sample…</span>
  }
  if (live.stale) {
    return (
      <span className="text-warning">
        Stale — last sample {formatRelativeDateTime(live.collected_at)}
      </span>
    )
  }
  return (
    <span className="text-fg-muted">Last sample {formatRelativeDateTime(live.collected_at)}</span>
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

/**
 * `state` is `_compute_state(warnings)` on the backend — derivable from
 * `warnings[]` alone — but it's rendered anyway, beside the title, as the
 * one fact a passing operator needs and the four KPI cards can't give: a
 * single verdict rather than four numbers to individually judge.
 */
const STATE_BADGE: Record<
  SystemHealthLiveResponse["state"],
  { label: string; tone: "success" | "warning" | "danger" }
> = {
  healthy: { label: "Healthy", tone: "success" },
  degraded: { label: "Degraded", tone: "warning" },
  critical: { label: "Critical", tone: "danger" },
}

/**
 * `warnings[]` carries no presentation strings by design — see
 * utils/healthWarnings.ts for the copy table and its open fallback. This is
 * the strip Figma doesn't draw at all: the backend computes threshold
 * breaches and, before this, nothing showed them — including
 * AI_HEARTBEAT_STALE, arguably the single most important signal on this page.
 */
function WarningsStrip({ warnings }: { warnings: HealthWarning[] }) {
  if (warnings.length === 0) return null

  return (
    <div className="mb-6 flex flex-col gap-2">
      {warnings.map((warning, index) => {
        const described = describeWarning(warning)
        return (
          <div
            key={`${warning.code}-${index}`}
            className={cn(
              "flex items-center gap-2 rounded-md border px-4 py-2.5 text-caption",
              described.tone === "danger"
                ? "border-danger-border bg-danger-subtle text-danger"
                : described.tone === "warning"
                  ? "border-warning-border bg-warning-subtle text-warning"
                  : "border-stroke bg-surface-1 text-fg-muted",
            )}
          >
            <RiAlertLine size={15} className="shrink-0" aria-hidden="true" />
            {described.message}
          </div>
        )
      })}
    </div>
  )
}

function GpuStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-stroke bg-canvas px-4 py-3">
      <div className="text-[10px] font-medium uppercase tracking-[0.08em] text-fg-muted">
        {label}
      </div>
      <div className="mt-1 text-secondary font-semibold text-fg">{value}</div>
    </div>
  )
}

/**
 * gpus[] is per-device, every metric nullable. Three cases, all real: zero
 * GPUs (the CI runner, any CPU-only box) is a stated absence, not an empty
 * table; one GPU renders its row and the live roll-ups are redundant with
 * it, so they're dropped; two or more is where the roll-ups earn their
 * place, because gpu_temp_max is the number that matters and the per-device
 * rows say which device is producing it.
 */
function GpuSection({ live }: { live: SystemHealthLiveResponse | undefined }) {
  if (!live) return null
  const gpus = live.gpus

  return (
    <div className="mb-8 rounded-xl border border-stroke bg-surface-1 p-5">
      <div className="mb-4 flex items-center gap-2">
        <RiCpuLine size={16} className="text-fg-muted" />
        <h3 className="text-xs font-medium text-fg-body">GPU</h3>
      </div>

      {gpus.length === 0 ? (
        <p className="text-caption text-fg-muted">No GPU detected on this machine.</p>
      ) : (
        <>
          {gpus.length > 1 ? (
            <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <GpuStat label="Usage (avg)" value={formatPercent(live.gpu_usage_avg)} />
              <GpuStat label="Temperature (max)" value={formatTemp(live.gpu_temp_max)} />
              <GpuStat label="Memory (max)" value={formatPercent(live.gpu_mem_pct_max)} />
            </div>
          ) : null}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-stroke text-fg-muted">
                  <th className="py-2 pr-4 text-xs font-medium">#</th>
                  <th className="py-2 pr-4 text-xs font-medium">Device</th>
                  <th className="py-2 pr-4 text-right text-xs font-medium">Usage</th>
                  <th className="py-2 pr-4 text-right text-xs font-medium">Temp</th>
                  <th className="py-2 text-right text-xs font-medium">Memory</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stroke">
                {gpus.map((gpu: GpuRead) => (
                  <tr key={gpu.index} className="text-fg-body">
                    <td className="py-2.5 pr-4 text-xs">{gpu.index}</td>
                    <td className="py-2.5 pr-4 text-xs" title={gpu.name}>
                      {truncateLabel(gpu.name, 32)}
                    </td>
                    <td className="py-2.5 pr-4 text-right text-xs">
                      {formatPercent(gpu.usage_percent)}
                    </td>
                    <td className="py-2.5 pr-4 text-right text-xs">{formatTemp(gpu.temp_c)}</td>
                    <td className="py-2.5 text-right text-xs">
                      {gpu.mem_used_mb !== null && gpu.mem_total_mb !== null
                        ? `${(gpu.mem_used_mb / 1024).toFixed(1)} / ${(gpu.mem_total_mb / 1024).toFixed(1)} GB`
                        : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
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

  const onlineQuery = useQuery({
    queryKey: ["system-online"],
    queryFn: getSystemHealth,
    refetchInterval: 30_000,
  })

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
  const isOnline = onlineQuery.data ?? null

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="mb-0.5 flex items-center gap-2.5">
            <h1 className="text-xl font-semibold text-fg">System Health</h1>
            {live ? (
              <Badge variant="subtle" tone={STATE_BADGE[live.state].tone}>
                {STATE_BADGE[live.state].label}
              </Badge>
            ) : null}
          </div>
          <p className="text-xs text-fg-muted">
            Oversee system diagnostics and hardware performance
          </p>
          <p className="mt-1 text-caption">{formatSampleStatus(live)}</p>
        </div>
        <div className="flex items-center gap-2">
          {isOnline === null ? (
            <span className="text-xs text-fg-muted">Checking status...</span>
          ) : isOnline ? (
            <div className="flex items-center gap-2 rounded-full border border-success-border bg-success-subtle px-3 py-1 text-xs font-medium text-success">
              <span className="h-2 w-2 rounded-full bg-success" />
              Online
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-full border border-danger-border bg-danger-subtle px-3 py-1 text-xs font-medium text-danger">
              <span className="h-2 w-2 rounded-full bg-danger" />
              Offline / Unreachable
            </div>
          )}
        </div>
      </div>

      {liveQuery.isError ? (
        <QueryErrorBanner
          error={liveQuery.error}
          fallback="Live health metrics unavailable."
          onRetry={() => liveQuery.refetch()}
        />
      ) : null}

      <WarningsStrip warnings={live?.warnings ?? []} />

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
          value={formatMs(live?.avg_inference_latency_ms)}
          isLoading={liveQuery.isLoading}
          subtext={formatSampleCameraSubtext(live)}
        />
        <StatCard
          icon={RiDashboard3Line}
          title="Processing Speed"
          value={formatFps(live?.avg_fps)}
          isLoading={liveQuery.isLoading}
          subtext={formatSampleCameraSubtext(live)}
        />
        <StatCard
          icon={RiHardDrive2Line}
          title="Disk Storage Usage"
          value={formatPercent(live?.disk_percent)}
          isLoading={liveQuery.isLoading}
          subtext={formatDiskSubtext(live)}
        />
      </div>

      <GpuSection live={live} />

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
