import type { ElementType } from "react"
import { useMemo } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import CalendarLineIcon from "remixicon-react/CalendarLineIcon"
import DownloadLineIcon from "remixicon-react/DownloadLineIcon"
import RefreshLineIcon from "remixicon-react/RefreshLineIcon"
import CarLineIcon from "remixicon-react/CarLineIcon"
import CheckboxLineIcon from "remixicon-react/CheckboxLineIcon"
import CameraLineIcon from "remixicon-react/CameraLineIcon"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  Tooltip,
} from "recharts"
import {
  exportDashboardAnalyticsCsv,
  getDashboardAnalytics,
} from "@/services/analytics"
import { getApiErrorMessage } from "@/utils/api"
import { formatHourLabel, truncateLabel } from "@/utils/analytics"

const DASHBOARD_QUERY_KEY = ["dashboard-analytics"] as const

interface MetricCardProps {
  icon: ElementType
  title: string
  value: string | number
  subtext?: string
}

function MetricCard({ icon: Icon, title, value, subtext }: MetricCardProps) {
  return (
    <div className="flex h-full flex-col justify-between rounded-xl border border-[#2A2A2A] bg-[#111111] p-5">
      <div>
        <div className="mb-5 flex h-9 w-9 items-center justify-center rounded-lg border border-[#2A2A2A] bg-[#1E1E1E]">
          <Icon size={17} className="text-[#A1A1AA]" />
        </div>
        <h4 className="mb-2 text-xs text-[#737373]">{title}</h4>
        <div className="leading-none tracking-tight text-white">
          <span className="text-[28px] font-semibold">{value}</span>
        </div>
      </div>
      {subtext ? <span className="mt-5 text-xs text-[#555]">{subtext}</span> : null}
    </div>
  )
}

export default function Dashboard() {
  const dashboardQuery = useQuery({
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: () => getDashboardAnalytics(),
  })

  const exportMutation = useMutation({
    mutationFn: () => exportDashboardAnalyticsCsv(),
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

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-white">Dashboard</h1>
        <p className="text-xs text-[#737373]">View analytical summaries & peak accident trends</p>
      </div>

      {dashboardQuery.isError ? (
        <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-[#F87171]/30 bg-[#F87171]/10 px-4 py-3">
          <p className="text-xs text-[#FCA5A5]">
            {getApiErrorMessage(dashboardQuery.error, "Unable to load dashboard analytics.")}
          </p>
          <button
            type="button"
            onClick={() => dashboardQuery.refetch()}
            className="rounded-md border border-[#333] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#1A1A1A]"
          >
            Retry
          </button>
        </div>
      ) : null}

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-1.5 text-xs text-[#D4D4D4]">
            <CalendarLineIcon size={13} className="text-[#737373]" />
            All time
          </div>
          <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-1.5 text-xs text-[#D4D4D4]">
            <CameraLineIcon size={13} className="text-[#737373]" />
            All cameras
          </div>
        </div>
        <button
          type="button"
          disabled={exportMutation.isPending}
          onClick={() => exportMutation.mutate()}
          className="flex items-center gap-2 rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <DownloadLineIcon size={13} />
          {exportMutation.isPending ? "Exporting..." : "Export"}
        </button>
      </div>

      {exportMutation.isError ? (
        <div className="mb-4 rounded-md border border-[#F87171]/30 bg-[#F87171]/10 px-4 py-3 text-xs text-[#FCA5A5]">
          {getApiErrorMessage(exportMutation.error, "Unable to export dashboard CSV.")}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-4">
        <div className="flex flex-col gap-5 lg:col-span-3">
          <div className="flex h-[260px] flex-col rounded-xl border border-[#2A2A2A] bg-[#111111] p-5">
            <h3 className="mb-4 text-xs font-medium text-[#D4D4D4]">Peak Accident Hours (24H)</h3>
            {dashboardQuery.isLoading ? (
              <div className="flex flex-1 items-center justify-center text-sm text-[#A1A1AA]">Loading chart...</div>
            ) : (
              <div className="flex-1 -ml-4">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={lineData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E1E1E" vertical={false} />
                    <XAxis
                      dataKey="time"
                      stroke="#333"
                      tick={{ fill: "#555", fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      dy={8}
                    />
                    <YAxis
                      allowDecimals={false}
                      stroke="#333"
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
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#fff"
                      strokeWidth={1.5}
                      dot={false}
                      activeDot={{ r: 4, fill: "#fff" }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
            {!dashboardQuery.isLoading && !chartHasData ? (
              <p className="mt-2 text-xs text-[#555]">No confirmed accidents found for the current view.</p>
            ) : null}
          </div>

          <div className="flex h-[330px] flex-col rounded-xl border border-[#2A2A2A] bg-[#111111] p-5">
            <h3 className="mb-4 text-xs font-medium text-[#D4D4D4]">Accident Frequency by Location</h3>
            {dashboardQuery.isLoading ? (
              <div className="flex flex-1 items-center justify-center text-sm text-[#A1A1AA]">Loading chart...</div>
            ) : locationHasData ? (
              <div className="flex-1 -ml-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                    <XAxis
                      type="number"
                      allowDecimals={false}
                      stroke="#333"
                      tick={{ fill: "#555", fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      dy={8}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      stroke="#333"
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
                      cursor={{ fill: "#1E1E1E" }}
                      formatter={(value) => [`${value} accidents`, "Volume"]}
                      labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName ?? ""}
                    />
                    <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={14}>
                      {barData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={index === 0 ? "#737373" : "#2A2A2A"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex flex-1 items-center justify-center text-sm text-[#A1A1AA]">
                No location data available yet.
              </div>
            )}
          </div>
        </div>

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
              subtext="Confirmed accidents"
            />
          </div>
          <div className="h-[195px]">
            <MetricCard
              icon={CheckboxLineIcon}
              title="Total Resolved"
              value={dashboardQuery.isLoading ? "..." : kpis?.total_resolved ?? 0}
              subtext="Closed incident records"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
