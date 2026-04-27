import { useState, type ElementType } from "react"
import { useQuery } from "@tanstack/react-query"
import ServerLineIcon from "remixicon-react/ServerLineIcon"
import TimerLineIcon from "remixicon-react/TimerLineIcon"
import Dashboard3LineIcon from "remixicon-react/Dashboard3LineIcon"
import HardDrive2LineIcon from "remixicon-react/HardDrive2LineIcon"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { getSystemHealth, getSystemHealthHistory, getSystemHealthLive } from "@/services/health"
import type { SystemHealthDataPoint } from "@/types/health"
import { getApiErrorMessage } from "@/utils/api"

// ─── helpers ────────────────────────────────────────────────────────────────

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${d}d ${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`
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

// ─── sub-components ──────────────────────────────────────────────────────────

interface HealthCardProps {
  icon: ElementType
  title: string
  value: string
  subtext?: string
}

function HealthCard({ icon: Icon, title, value, subtext }: HealthCardProps) {
  return (
    <div className="flex h-full min-h-[160px] flex-col justify-between rounded-xl border border-[#2A2A2A] bg-[#111111] p-5">
      <div>
        <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg border border-[#2A2A2A] bg-[#1E1E1E]">
          <Icon size={17} className="text-[#A1A1AA]" />
        </div>
        <h4 className="mb-2 min-h-[32px] text-[11px] font-medium uppercase tracking-wider text-[#737373]">
          {title}
        </h4>
        <div className="text-3xl font-semibold leading-none tracking-tight text-white">{value}</div>
      </div>
      {subtext ? <div className="mt-4 text-xs text-[#555]">{subtext}</div> : null}
    </div>
  )
}

interface HealthChartProps {
  title: string
  data: SystemHealthDataPoint[]
  dataKey: keyof SystemHealthDataPoint
  color: string
  range: "48h" | "30d"
  unit?: string
  isLoading: boolean
}

function HealthChart({ title, data, dataKey, color, range, unit = "%", isLoading }: HealthChartProps) {
  const chartData = data.map((point) => ({
    time: formatTimestamp(point.timestamp, range),
    value: point[dataKey] as number,
  }))

  return (
    <div className="flex h-[260px] flex-col rounded-xl border border-[#2A2A2A] bg-[#111111] p-5">
      <h3 className="mb-4 text-xs font-medium text-[#D4D4D4]">{title}</h3>
      {isLoading ? (
        <div className="flex flex-1 items-center justify-center text-xs text-[#555]">Loading...</div>
      ) : data.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-xs text-[#555]">No data available</div>
      ) : (
        <div className="flex-1 -ml-4">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id={`grad-${title.replace(/\s+/g, "")}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.15} />
                  <stop offset="95%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E1E1E" vertical={false} />
              <XAxis
                dataKey="time"
                stroke="#333"
                tick={{ fill: "#555", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                dy={8}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[0, 100]}
                stroke="#333"
                tick={{ fill: "#555", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={32}
                tickFormatter={(v) => `${v}${unit}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1A1A1A",
                  border: "1px solid #2A2A2A",
                  borderRadius: "6px",
                  fontSize: 12,
                }}
                itemStyle={{ color: "#E4E4E7" }}
                labelStyle={{ color: "#737373" }}
                formatter={(v) => [`${Number(v).toFixed(1)}${unit}`, title]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={1.5}
                fillOpacity={1}
                fill={`url(#grad-${title.replace(/\s+/g, "")})`}
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
  const historyData = historyQuery.data?.data ?? []
  const isOnline = onlineQuery.data ?? null

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="mb-0.5 text-xl font-semibold text-white">System Health</h1>
          <p className="text-xs text-[#737373]">Oversee system diagnostics and hardware performance</p>
        </div>
        <div className="flex items-center gap-2">
          {isOnline === null ? (
            <span className="text-xs text-[#737373]">Checking status...</span>
          ) : isOnline ? (
            <div className="flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              Online
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-full border border-[#F87171]/30 bg-[#F87171]/10 px-3 py-1 text-xs font-medium text-[#F87171]">
              <span className="h-2 w-2 rounded-full bg-[#F87171]" />
              Offline / Unreachable
            </div>
          )}
        </div>
      </div>

      {liveQuery.isError ? (
        <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-[#F87171]/30 bg-[#F87171]/10 px-4 py-3">
          <p className="text-xs text-[#FCA5A5]">
            {getApiErrorMessage(liveQuery.error, "Live health metrics unavailable.")}
          </p>
          <button
            type="button"
            onClick={() => liveQuery.refetch()}
            className="rounded-md border border-[#333] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#1A1A1A]"
          >
            Retry
          </button>
        </div>
      ) : null}

      <div className="mb-8 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
        <HealthCard
          icon={ServerLineIcon}
          title="Server Uptime"
          value={liveQuery.isLoading ? "..." : live ? formatUptime(live.uptime_seconds) : "N/A"}
        />
        <HealthCard
          icon={TimerLineIcon}
          title="Inference Latency"
          value={liveQuery.isLoading ? "..." : formatMs(live?.avg_inference_latency_ms)}
          subtext="Average AI inference time"
        />
        <HealthCard
          icon={Dashboard3LineIcon}
          title="Processing Speed"
          value={liveQuery.isLoading ? "..." : formatFps(live?.avg_fps)}
          subtext="Average frames per second"
        />
        <HealthCard
          icon={HardDrive2LineIcon}
          title="Disk Storage Usage"
          value={liveQuery.isLoading ? "..." : formatPercent(live?.disk_usage_percent)}
          subtext={
            live
              ? `${live.disk_used_gb.toFixed(1)} GB / ${live.disk_total_gb.toFixed(1)} GB`
              : undefined
          }
        />
      </div>

      <div className="mb-5 flex items-center gap-4">
        <button
          type="button"
          onClick={() => setActiveTab("48h")}
          className={`rounded-full px-4 py-1.5 text-xs font-medium transition-colors ${
            activeTab === "48h"
              ? "border border-[#333] bg-[#1E1E1E] text-white"
              : "text-[#737373] hover:text-[#D4D4D4]"
          }`}
        >
          Last 48 Hours
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("30d")}
          className={`rounded-full px-4 py-1.5 text-xs font-medium transition-colors ${
            activeTab === "30d"
              ? "border border-[#333] bg-[#1E1E1E] text-white"
              : "text-[#737373] hover:text-[#D4D4D4]"
          }`}
        >
          30-Day Trend
        </button>
      </div>

      {historyQuery.isError ? (
        <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-[#F87171]/30 bg-[#F87171]/10 px-4 py-3">
          <p className="text-xs text-[#FCA5A5]">
            {getApiErrorMessage(historyQuery.error, "Historical health data unavailable.")}
          </p>
          <button
            type="button"
            onClick={() => historyQuery.refetch()}
            className="rounded-md border border-[#333] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#1A1A1A]"
          >
            Retry
          </button>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <HealthChart
          title="CPU Utilization"
          data={historyData}
          dataKey="cpu_usage"
          color="#ffffff"
          range={activeTab}
          isLoading={historyQuery.isLoading}
        />
        <HealthChart
          title="GPU Utilization"
          data={historyData}
          dataKey="gpu_usage"
          color="#ffffff"
          range={activeTab}
          isLoading={historyQuery.isLoading}
        />
        <HealthChart
          title="GPU Temperature"
          data={historyData}
          dataKey="gpu_temperature"
          color="#ef4444"
          range={activeTab}
          unit="°C"
          isLoading={historyQuery.isLoading}
        />
        <HealthChart
          title="RAM Utilization"
          data={historyData}
          dataKey="ram_usage"
          color="#ffffff"
          range={activeTab}
          isLoading={historyQuery.isLoading}
        />
      </div>
    </div>
  )
}
