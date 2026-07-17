import type { ElementType } from "react"
import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import CalendarLineIcon from "remixicon-react/CalendarLineIcon"
import DownloadLineIcon from "remixicon-react/DownloadLineIcon"
import RefreshLineIcon from "remixicon-react/RefreshLineIcon"
import CarLineIcon from "remixicon-react/CarLineIcon"
import CheckboxLineIcon from "remixicon-react/CheckboxLineIcon"
import CameraLineIcon from "remixicon-react/CameraLineIcon"
import CloseLineIcon from "remixicon-react/CloseLineIcon"
import {
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  BarChart,
  Bar,
  Tooltip,
  Area,
  AreaChart,
  Cell,
} from "recharts"
import {
  exportDashboardAnalyticsCsv,
  getDashboardAnalytics,
} from "@/services/analytics"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { formatHourLabel, truncateLabel } from "@/utils/analytics"
import type { AnalyticsFilters } from "@/types/analytics"

interface MetricCardProps {
  icon: ElementType
  title: string
  value: string | number
  subtext?: string
  delta?: string
  deltaPositive?: boolean
}

function MetricCard({ icon: Icon, title, value, subtext, delta, deltaPositive }: MetricCardProps) {
  return (
    <div className="flex h-full flex-col justify-between rounded-xl border border-[#222] bg-linear-to-b from-[#1a1a1a] to-[#111] p-5 shadow-lg">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-[#2A2A2A] bg-[#1E1E1E]">
        <Icon size={18} className="text-[#A1A1AA]" />
      </div>
      <div>
        <h4 className="mb-2 text-xs text-[#737373]">{title}</h4>
        <div className="flex items-end gap-3">
          <span className="text-[32px] font-semibold leading-none tracking-tight text-white">{value}</span>
          {delta ? (
            <span className={`mb-1 text-xs font-medium ${deltaPositive ? "text-emerald-400" : "text-red-400"}`}>
              {delta}
            </span>
          ) : null}
        </div>
        {subtext ? <p className="mt-2 text-xs text-[#555]">{subtext}</p> : null}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [cameraId, setCameraId] = useState("")

  const filters: AnalyticsFilters = {
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    camera_id: cameraId ? [Number(cameraId)] : undefined,
  }

  const hasFilters = Boolean(startDate || endDate || cameraId)

  const camerasQuery = useCameraOptions()

  const dashboardQuery = useQuery({
    queryKey: ["dashboard-analytics", filters],
    queryFn: () => getDashboardAnalytics(filters),
  })

  const exportMutation = useMutation({
    mutationFn: () => exportDashboardAnalyticsCsv(filters),
  })

  const lineData = useMemo(
    () =>
      (dashboardQuery.data?.peak_accident_times ?? []).map((item) => ({
        time: formatHourLabel(item.hour),
        value: item.count,
      })),
    [dashboardQuery.data?.peak_accident_times],
  )

  const barData = useMemo(
    () =>
      (dashboardQuery.data?.frequency_by_location ?? []).slice(0, 10).map((item) => ({
        name: truncateLabel(item.camera_name),
        fullName: item.camera_name,
        value: item.accident_count,
      })),
    [dashboardQuery.data?.frequency_by_location],
  )

  const kpis = dashboardQuery.data?.kpis
  const chartHasData = lineData.some((item) => item.value > 0)
  const locationHasData = barData.length > 0
  const maxBarValue = barData.length > 0 ? Math.max(...barData.map((d) => d.value)) : 1

  return (
    <div className="min-h-screen bg-[#0A0A0A] p-8">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <div className="mb-6">
          <h1 className="mb-0.5 text-xl font-semibold text-white">Dashboard</h1>
          <p className="text-xs text-[#555]">View analytical summaries &amp; peak accident trends</p>
        </div>

        {dashboardQuery.isError ? (
          <QueryErrorBanner
            error={dashboardQuery.error}
            fallback="Unable to load dashboard analytics."
            onRetry={() => dashboardQuery.refetch()}
          />
        ) : null}

        {/* Toolbar */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1">
              <CalendarLineIcon size={13} className="text-[#737373]" />
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="bg-transparent text-xs text-[#D4D4D4] focus:outline-none [color-scheme:dark]"
                placeholder="Start date"
              />
            </div>
            <span className="text-xs text-[#555]">to</span>
            <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1">
              <CalendarLineIcon size={13} className="text-[#737373]" />
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="bg-transparent text-xs text-[#D4D4D4] focus:outline-none [color-scheme:dark]"
                placeholder="End date"
              />
            </div>
            <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1">
              <CameraLineIcon size={13} className="text-[#737373]" />
              <select
                value={cameraId}
                onChange={(e) => setCameraId(e.target.value)}
                className="bg-transparent text-xs text-[#D4D4D4] focus:outline-none"
              >
                <option value="">All cameras</option>
                {camerasQuery.data?.cameras.map((c) => (
                  <option key={c.camera_id} value={c.camera_id}>
                    {c.camera_name}
                  </option>
                ))}
              </select>
            </div>
            {hasFilters ? (
              <button
                type="button"
                onClick={() => { setStartDate(""); setEndDate(""); setCameraId("") }}
                className="flex items-center gap-1 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1.5 text-xs text-[#737373] transition-colors hover:text-white"
              >
                <CloseLineIcon size={12} />
                Clear
              </button>
            ) : null}
          </div>
          <button
            type="button"
            disabled={exportMutation.isPending}
            onClick={() => exportMutation.mutate()}
            className="flex items-center gap-2 rounded-md border border-[#333] bg-[#1A1A1A] px-4 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-[#222] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <DownloadLineIcon size={13} />
            {exportMutation.isPending ? "Exporting..." : "Export"}
          </button>
        </div>

        {exportMutation.isError ? (
          <QueryErrorBanner error={exportMutation.error} fallback="Unable to export dashboard CSV." />
        ) : null}

        {/* Main grid */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-4">
          {/* Charts column */}
          <div className="flex flex-col gap-5 lg:col-span-3">

            {/* Peak Accident Hours — Area chart with gradient fill */}
            <div className="flex h-[270px] flex-col rounded-xl border border-[#222] bg-linear-to-b from-[#161616] to-[#0f0f0f] p-5 shadow-lg">
              <h3 className="mb-4 text-xs font-medium text-[#D4D4D4]">Peak Accident Hours (24H)</h3>
              {dashboardQuery.isLoading ? (
                <div className="flex flex-1 items-center justify-center text-sm text-[#555]">Loading chart...</div>
              ) : (
                <div className="flex-1 -ml-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={lineData}>
                      <defs>
                        <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#ffffff" stopOpacity={0.18} />
                          <stop offset="100%" stopColor="#ffffff" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E1E1E" vertical={false} />
                      <XAxis
                        dataKey="time"
                        stroke="#222"
                        tick={{ fill: "#555", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        dy={8}
                      />
                      <YAxis
                        allowDecimals={false}
                        stroke="#222"
                        tick={{ fill: "#555", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        width={28}
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
                        cursor={{ stroke: "#333", strokeWidth: 1 }}
                        formatter={(value) => [`${value} accidents`, "Volume"]}
                        labelFormatter={(label) => `${label}:00`}
                      />
                      <Area
                        type="monotone"
                        dataKey="value"
                        stroke="#ffffff"
                        strokeWidth={1.5}
                        fill="url(#areaGradient)"
                        dot={false}
                        activeDot={{ r: 4, fill: "#fff", stroke: "#fff" }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
              {!dashboardQuery.isLoading && !chartHasData ? (
                <p className="mt-2 text-xs text-[#555]">No confirmed accidents found for the current view.</p>
              ) : null}
            </div>

            {/* Accident Frequency by Location — gradient bars */}
            <div className="flex h-[340px] flex-col rounded-xl border border-[#222] bg-linear-to-b from-[#161616] to-[#0f0f0f] p-5 shadow-lg">
              <h3 className="mb-4 text-xs font-medium text-[#D4D4D4]">Accident Frequency by Location</h3>
              {dashboardQuery.isLoading ? (
                <div className="flex flex-1 items-center justify-center text-sm text-[#555]">Loading chart...</div>
              ) : locationHasData ? (
                <div className="flex-1 -ml-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={barData} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                      <defs>
                        {barData.map((entry, index) => {
                          const ratio = entry.value / maxBarValue
                          const lightness = Math.round(30 + ratio * 45)
                          return (
                            <linearGradient key={`grad-${index}`} id={`barGrad-${index}`} x1="0" y1="0" x2="1" y2="0">
                              <stop offset="0%" stopColor={`hsl(0,0%,${lightness}%)`} stopOpacity={1} />
                              <stop offset="100%" stopColor={`hsl(0,0%,${Math.max(lightness - 15, 15)}%)`} stopOpacity={1} />
                            </linearGradient>
                          )
                        })}
                      </defs>
                      <XAxis
                        type="number"
                        allowDecimals={false}
                        stroke="#222"
                        tick={{ fill: "#555", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        dy={8}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        stroke="#222"
                        tick={{ fill: "#737373", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        width={110}
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
                        cursor={{ fill: "rgba(255,255,255,0.03)" }}
                        formatter={(value) => [`${value} accidents`, "Volume"]}
                        labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName ?? ""}
                      />
                      <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={13}>
                        {barData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={`url(#barGrad-${index})`} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="flex flex-1 items-center justify-center text-sm text-[#555]">
                  No location data available yet.
                </div>
              )}
            </div>
          </div>

          {/* KPI cards column */}
          <div className="flex flex-col gap-5">
            <div className="h-[195px]">
              <MetricCard
                icon={RefreshLineIcon}
                title="Ongoing Accidents"
                value={dashboardQuery.isLoading ? "..." : kpis?.ongoing ?? 0}
                subtext="Live incident queue"
              />
            </div>
            <div className="h-[195px]">
              <MetricCard
                icon={CarLineIcon}
                title="Total Accidents"
                value={dashboardQuery.isLoading ? "..." : kpis?.total_accidents ?? 0}
                subtext="Compared to last month"
              />
            </div>
            <div className="h-[195px]">
              <MetricCard
                icon={CheckboxLineIcon}
                title="Total Resolved"
                value={dashboardQuery.isLoading ? "..." : kpis?.total_resolved ?? 0}
                subtext="Compared to last month"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
