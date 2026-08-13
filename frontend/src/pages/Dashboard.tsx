import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

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
import { exportDashboardAnalyticsCsv, getDashboardAnalytics } from "@/api/analytics"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { StatCard } from "@/components/ui/StatCard"
import { formatHourLabel, truncateLabel } from "@/utils/analytics"
import type { AnalyticsFilters } from "@/api/analytics"
import {
  RiCalendarLine,
  RiCameraLine,
  RiCarLine,
  RiCheckboxLine,
  RiCloseLine,
  RiDownloadLine,
  RiRefreshLine,
} from "@remixicon/react"

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
    <div className="min-h-screen bg-canvas p-8">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <div className="mb-6">
          <h1 className="mb-0.5 text-xl font-semibold text-fg">Dashboard</h1>
          <p className="text-xs text-fg-muted">
            View analytical summaries &amp; peak accident trends
          </p>
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
            <div className="flex items-center gap-2 rounded-md border border-stroke bg-surface-1 px-2 py-1">
              <RiCalendarLine size={13} className="text-fg-muted" />
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="bg-transparent text-xs text-fg-body focus:outline-none [color-scheme:dark]"
                placeholder="Start date"
              />
            </div>
            <span className="text-xs text-fg-muted">to</span>
            <div className="flex items-center gap-2 rounded-md border border-stroke bg-surface-1 px-2 py-1">
              <RiCalendarLine size={13} className="text-fg-muted" />
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="bg-transparent text-xs text-fg-body focus:outline-none [color-scheme:dark]"
                placeholder="End date"
              />
            </div>
            <div className="flex items-center gap-2 rounded-md border border-stroke bg-surface-1 px-2 py-1">
              <RiCameraLine size={13} className="text-fg-muted" />
              <select
                value={cameraId}
                onChange={(e) => setCameraId(e.target.value)}
                className="bg-transparent text-xs text-fg-body focus:outline-none"
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
                onClick={() => {
                  setStartDate("")
                  setEndDate("")
                  setCameraId("")
                }}
                className="flex items-center gap-1 rounded-md border border-stroke bg-surface-1 px-2 py-1.5 text-xs text-fg-muted transition-colors hover:text-fg"
              >
                <RiCloseLine size={12} />
                Clear
              </button>
            ) : null}
          </div>
          <button
            type="button"
            disabled={exportMutation.isPending}
            onClick={() => exportMutation.mutate()}
            className="flex items-center gap-2 rounded-md border border-stroke-strong bg-surface-1 px-4 py-1.5 text-xs font-semibold text-fg transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RiDownloadLine size={13} />
            {exportMutation.isPending ? "Exporting..." : "Export"}
          </button>
        </div>

        {exportMutation.isError ? (
          <QueryErrorBanner
            error={exportMutation.error}
            fallback="Unable to export dashboard CSV."
          />
        ) : null}

        {/* Main grid */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-4">
          {/* Charts column */}
          <div className="flex flex-col gap-5 lg:col-span-3">
            {/* Peak Accident Hours — Area chart with gradient fill */}
            <div className="flex h-[270px] flex-col rounded-xl border border-stroke bg-linear-to-b from-surface-1 to-canvas p-5 shadow-lg">
              <h3 className="mb-4 text-xs font-medium text-fg-body">Peak Accident Hours (24H)</h3>
              {dashboardQuery.isLoading ? (
                <div className="flex flex-1 items-center justify-center text-sm text-fg-muted">
                  Loading chart...
                </div>
              ) : (
                <div className="flex-1 -ml-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={lineData}>
                      <defs>
                        <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--color-chart-fill-from)" />
                          <stop offset="100%" stopColor="var(--color-chart-fill-to)" />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="var(--color-chart-grid)"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="time"
                        stroke="var(--color-chart-grid)"
                        tick={{ fill: "var(--color-chart-axis)", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        dy={8}
                      />
                      <YAxis
                        allowDecimals={false}
                        stroke="var(--color-chart-grid)"
                        tick={{ fill: "var(--color-chart-axis)", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        width={28}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "var(--color-surface-1)",
                          border: "1px solid var(--color-stroke)",
                          borderRadius: "6px",
                          fontSize: 12,
                        }}
                        itemStyle={{ color: "var(--color-fg-body)" }}
                        labelStyle={{ color: "var(--color-fg-muted)" }}
                        cursor={{ stroke: "var(--color-stroke-strong)", strokeWidth: 1 }}
                        formatter={(value) => [`${value} accidents`, "Volume"]}
                        labelFormatter={(label) => `${label}:00`}
                      />
                      <Area
                        type="monotone"
                        dataKey="value"
                        stroke="var(--color-chart-line)"
                        strokeWidth={1.5}
                        fill="url(#areaGradient)"
                        dot={false}
                        activeDot={{
                          r: 4,
                          fill: "var(--color-chart-line)",
                          stroke: "var(--color-chart-line)",
                        }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
              {!dashboardQuery.isLoading && !chartHasData ? (
                <p className="mt-2 text-xs text-fg-muted">
                  No confirmed accidents found for the current view.
                </p>
              ) : null}
            </div>

            {/* Accident Frequency by Location — gradient bars */}
            <div className="flex h-[340px] flex-col rounded-xl border border-stroke bg-linear-to-b from-surface-1 to-canvas p-5 shadow-lg">
              <h3 className="mb-4 text-xs font-medium text-fg-body">
                Accident Frequency by Location
              </h3>
              {dashboardQuery.isLoading ? (
                <div className="flex flex-1 items-center justify-center text-sm text-fg-muted">
                  Loading chart...
                </div>
              ) : locationHasData ? (
                <div className="flex-1 -ml-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={barData}
                      layout="vertical"
                      margin={{ top: 0, right: 16, left: 0, bottom: 0 }}
                    >
                      <defs>
                        {barData.map((entry, index) => {
                          const ratio = entry.value / maxBarValue
                          const lightness = Math.round(30 + ratio * 45)
                          return (
                            <linearGradient
                              key={`grad-${index}`}
                              id={`barGrad-${index}`}
                              x1="0"
                              y1="0"
                              x2="1"
                              y2="0"
                            >
                              <stop
                                offset="0%"
                                stopColor={`hsl(0,0%,${lightness}%)`}
                                stopOpacity={1}
                              />
                              <stop
                                offset="100%"
                                stopColor={`hsl(0,0%,${Math.max(lightness - 15, 15)}%)`}
                                stopOpacity={1}
                              />
                            </linearGradient>
                          )
                        })}
                      </defs>
                      <XAxis
                        type="number"
                        allowDecimals={false}
                        stroke="var(--color-chart-grid)"
                        tick={{ fill: "var(--color-chart-axis)", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        dy={8}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        stroke="var(--color-chart-grid)"
                        tick={{ fill: "var(--color-chart-axis)", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        width={110}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "var(--color-surface-1)",
                          border: "1px solid var(--color-stroke)",
                          borderRadius: "6px",
                          fontSize: 12,
                        }}
                        itemStyle={{ color: "var(--color-fg-body)" }}
                        labelStyle={{ color: "var(--color-fg-muted)" }}
                        cursor={{ fill: "var(--color-chart-line)", fillOpacity: 0.03 }}
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
                <div className="flex flex-1 items-center justify-center text-sm text-fg-muted">
                  No location data available yet.
                </div>
              )}
            </div>
          </div>

          {/* KPI cards column */}
          <div className="flex flex-col gap-5">
            <div className="h-[195px]">
              <StatCard
                icon={RiRefreshLine}
                title="Ongoing Accidents"
                value={dashboardQuery.isLoading ? "..." : (kpis?.ongoing ?? 0)}
                subtext="Live incident queue"
              />
            </div>
            <div className="h-[195px]">
              <StatCard
                icon={RiCarLine}
                title="Total Accidents"
                value={dashboardQuery.isLoading ? "..." : (kpis?.total_accidents ?? 0)}
                subtext="Compared to last month"
              />
            </div>
            <div className="h-[195px]">
              <StatCard
                icon={RiCheckboxLine}
                title="Total Resolved"
                value={dashboardQuery.isLoading ? "..." : (kpis?.total_resolved ?? 0)}
                subtext="Compared to last month"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
