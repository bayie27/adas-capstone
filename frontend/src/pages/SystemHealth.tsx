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
import { Badge, BadgeDot } from "@/components/ui/Badge"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { StatCard } from "@/components/ui/StatCard"
import { Tabs } from "@/components/ui/Tabs"
import { getSystemHealthHistory, getSystemHealthLive } from "@/api/health"
import type { GpuRead, SystemHealthDataPoint, SystemHealthLiveResponse } from "@/api/health"
import { getOperatorWarningEntry } from "@/utils/warningCopy"
import { formatRelativeDateTime } from "@/utils/datetime"
import { truncateLabel } from "@/utils/format"
import { cn } from "@/utils/cn"
import {
  RiAlertLine,
  RiCheckboxCircleLine,
  RiCpuLine,
  RiDashboard3Line,
  RiHardDrive2Line,
  RiServerLine,
  RiShieldCheckLine,
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

// ─── Hardware health card ────────────────────────────────────────────────────

/**
 * Compact operator-facing hardware status card with two rows.
 * Derives plain-language status from existing live fields and warning codes —
 * no new API fields needed. Placed above the technical accordion so operators
 * see hardware status without needing to expand technical details.
 */
function HardwareHealthRow({
  label,
  tone,
  statusText,
}: {
  label: string
  tone: "success" | "warning" | "danger" | "neutral"
  statusText: string
}) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-stroke last:border-b-0">
      <span className="text-xs font-medium text-fg-muted uppercase tracking-[0.08em]">{label}</span>
      <div className="flex items-center gap-2">
        <BadgeDot tone={tone} />
        <span className="text-xs text-fg-body">{statusText}</span>
      </div>
    </div>
  )
}

function HardwareHealthCard({ live }: { live: SystemHealthLiveResponse | undefined }) {
  if (!live) return null

  const hasGpuTempCritical = (live.warnings ?? []).some((w) => w.code === "GPU_TEMP_CRITICAL")
  const hasRamCritical = (live.warnings ?? []).some((w) => w.code === "RAM_CRITICAL")

  // GPU row
  let gpuTone: "success" | "warning" | "danger" | "neutral"
  let gpuText: string
  if (live.gpus.length === 0) {
    gpuTone = "neutral"
    gpuText = "No graphics processor detected"
  } else if (hasGpuTempCritical) {
    gpuTone = "danger"
    gpuText = `Overheating${live.gpu_temp_max != null ? ` (${live.gpu_temp_max.toFixed(0)}°C)` : ""}`
  } else {
    gpuTone = "success"
    gpuText = `Working normally${live.gpu_temp_max != null ? ` (${live.gpu_temp_max.toFixed(0)}°C)` : ""}`
  }

  // CPU / memory row
  let memTone: "success" | "warning" | "danger" | "neutral"
  let memText: string
  if (hasRamCritical) {
    memTone = "danger"
    memText = `Memory almost full${live.ram_usage != null ? ` (${live.ram_usage.toFixed(0)}%)` : ""}`
  } else {
    memTone = "success"
    memText = `Running normally${live.cpu_usage != null ? ` · CPU ${live.cpu_usage.toFixed(0)}%` : ""}`
  }

  return (
    <div className="mb-8 rounded-xl border border-stroke bg-surface-1 p-5">
      <div className="mb-3 flex items-center gap-2">
        <RiCpuLine size={16} className="text-fg-muted" />
        <h3 className="text-xs font-medium text-fg-body">Hardware Health</h3>
      </div>
      <HardwareHealthRow label="Graphics processor" tone={gpuTone} statusText={gpuText} />
      <HardwareHealthRow label="Processor & memory" tone={memTone} statusText={memText} />
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

// ─── GPU section ─────────────────────────────────────────────────────────────

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

function DiagnosticRow({ label, explanation }: { label: string; explanation: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-stroke py-3 last:border-b-0">
      <div>
        <div className="text-xs font-medium text-fg-body">{label}</div>
        <p className="mt-1 text-caption text-fg-muted">{explanation}</p>
      </div>
      <Badge
        tone="neutral"
        variant="subtle"
        uppercase={false}
        className="shrink-0 whitespace-nowrap"
      >
        Unavailable — logged server-side only
      </Badge>
    </div>
  )
}

/**
 * Two heartbeat-time checks (`_check_engine_identity`, `_check_clock_skew` —
 * `backend/app/api/routes/internal.py`) run on every heartbeat but only ever
 * log a warning — neither is persisted to a table or returned by any
 * response, so this section always reads Unavailable today (G7). Neither
 * check has ever emitted a structured code of its own — unlike the five real
 * `HealthWarning` codes `_build_warnings` does emit (`system_health.py:64`),
 * which power `WarningsStrip` above and are unrelated to these two checks.
 * This section has no code to react to and does not invent one.
 */
function EngineDiagnosticsSection() {
  return (
    <div className="mb-8 rounded-xl border border-stroke bg-surface-1 p-5">
      <div className="mb-4 flex items-center gap-2">
        <RiShieldCheckLine size={16} className="text-fg-muted" />
        <h3 className="text-xs font-medium text-fg-body">Engine Diagnostics</h3>
      </div>

      <DiagnosticRow
        label="Two-engine conflict"
        explanation="Warns when a second engine_id heartbeats within the stale window of a different one -- e.g. two engine processes pointed at the same backend."
      />
      <DiagnosticRow
        label="Engine clock skew"
        explanation="Warns when a heartbeat's own sent_at disagrees with server time by more than 10 seconds -- a sign the engine's clock has drifted."
      />
    </div>
  )
}

function CapacityRow({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-xs">
      <span className="font-medium tracking-[0.08em] text-fg-muted">{label}</span>
      <Badge tone="neutral" variant="subtle" uppercase={false}>
        Unavailable
      </Badge>
    </div>
  )
}

/**
 * `ai_engine/capacity.py` benchmarks the machine once at startup and writes
 * `machine_profile.json` (device, chosen camera capacity, the FPS band the
 * decision was made against) — gitignored, machine-local, and never
 * transmitted to the backend (G8). Mounted live today, same as
 * EngineDiagnosticsSection, always Unavailable until that changes.
 */
function MachineCapacitySection() {
  return (
    <div className="mb-8 rounded-xl border border-stroke bg-surface-1 p-5">
      <div className="mb-4 flex items-center gap-2">
        <RiServerLine size={16} className="text-fg-muted" />
        <h3 className="text-xs font-medium text-fg-body">Machine Capacity</h3>
      </div>

      <CapacityRow label="Device" />
      <CapacityRow label="Chosen camera capacity" />
      <CapacityRow label="FPS band" />

      {/* CLAUDE.md, verbatim, on ai_engine/machine_profile.json's absence: */}
      <p className="mt-3 text-caption text-fg-muted">
        "Absence is not an error — the engine falls back to a conservative one camera and says so on
        startup."
      </p>
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
  const [techDetailsOpen, setTechDetailsOpen] = useState(false)

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

      {/* ── Hardware health summary card ────────────────────────────────── */}
      <HardwareHealthCard live={live} />

      {/* ── Technical details accordion ─────────────────────────────────── */}
      <details
        open={techDetailsOpen}
        onToggle={(e) => setTechDetailsOpen((e.currentTarget as HTMLDetailsElement).open)}
        className="rounded-xl border border-stroke bg-surface-1"
      >
        <summary className="flex cursor-pointer select-none items-center justify-between px-5 py-4 text-sm font-medium text-fg hover:bg-surface-2 rounded-xl transition-colors duration-150 [&::-webkit-details-marker]:hidden list-none">
          <span>Advance details</span>
          <span
            className={cn(
              "text-fg-muted transition-transform duration-200",
              techDetailsOpen ? "rotate-180" : "rotate-0",
            )}
            aria-hidden="true"
          >
            ▾
          </span>
        </summary>

        <div className="px-5 pb-5 pt-2">
          {/* GPU table — existing component, moved here unchanged */}
          <GpuSection live={live} />

          {/* Engine Diagnostics — existing component, verbatim copy */}
          <EngineDiagnosticsSection />

          {/* Machine Capacity — existing component, verbatim copy */}
          <MachineCapacitySection />

          {/* History range tabs + 6 charts */}
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
                  <LiveReading
                    value={live.cpu_usage}
                    available={live.cpu_usage_available}
                    unit="%"
                  />
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
                  <LiveReading
                    value={live.ram_usage}
                    available={live.ram_usage_available}
                    unit="%"
                  />
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
                  <LiveReading
                    value={live.cpu_temp}
                    available={live.cpu_temp_available}
                    unit="°C"
                  />
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
      </details>
    </div>
  )
}
