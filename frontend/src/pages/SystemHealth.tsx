import { useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { AreaChartCard } from "@/components/charts/AreaChartCard"
import { CHART } from "@/components/charts/chartTheme"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { StatCard } from "@/components/ui/StatCard"
import { Tabs } from "@/components/ui/Tabs"
import { getSystemHealth, getSystemHealthHistory, getSystemHealthLive } from "@/api/health"
import type { HealthWarning, SystemHealthDataPoint, SystemHealthLiveResponse } from "@/api/health"
import { describeWarning } from "@/utils/healthWarnings"
import { cn } from "@/utils/cn"
import {
  RiAlertLine,
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
  const { disk_used_bytes: used, disk_total_bytes: total } = live
  if (used == null || total == null) return undefined
  return `${(used / BYTES_PER_GB).toFixed(1)} GB / ${(total / BYTES_PER_GB).toFixed(1)} GB`
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
          <h1 className="mb-0.5 text-xl font-semibold text-fg">System Health</h1>
          <p className="text-xs text-fg-muted">
            Oversee system diagnostics and hardware performance
          </p>
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
        />
        <StatCard
          icon={RiTimerLine}
          title="Inference Latency"
          value={formatMs(live?.avg_inference_latency_ms)}
          isLoading={liveQuery.isLoading}
          subtext="Average AI inference time"
        />
        <StatCard
          icon={RiDashboard3Line}
          title="Processing Speed"
          value={formatFps(live?.avg_fps)}
          isLoading={liveQuery.isLoading}
          subtext="Average frames per second"
        />
        <StatCard
          icon={RiHardDrive2Line}
          title="Disk Storage Usage"
          value={formatPercent(live?.disk_percent)}
          isLoading={liveQuery.isLoading}
          subtext={formatDiskSubtext(live)}
        />
      </div>

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
        />
      </div>
    </div>
  )
}
