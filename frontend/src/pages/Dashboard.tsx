import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { exportDashboardAnalyticsCsv, getDashboardAnalytics } from "@/api/analytics"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { AreaChartCard } from "@/components/charts/AreaChartCard"
import { BarChartCard } from "@/components/charts/BarChartCard"
import { Button } from "@/components/ui/Button"
import { DateRangePicker } from "@/components/ui/DateRangePicker"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { StatCard } from "@/components/ui/StatCard"
import { formatHourLabel, truncateLabel } from "@/utils/format"
import type { AnalyticsFilters } from "@/api/analytics"
import {
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

  const cameraOptions = [
    { value: "", label: "All cameras" },
    ...(camerasQuery.data?.cameras ?? []).map((c) => ({
      value: String(c.camera_id),
      label: c.camera_name,
    })),
  ]

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
            <DateRangePicker
              start={startDate}
              end={endDate}
              onStartChange={setStartDate}
              onEndChange={setEndDate}
              label="Filter analytics by date"
            />
            <FilterSelect value={cameraId} options={cameraOptions} onChange={setCameraId} />
            {hasFilters ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setStartDate("")
                  setEndDate("")
                  setCameraId("")
                }}
              >
                <RiCloseLine size={13} />
                Clear
              </Button>
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
            <AreaChartCard
              title="Peak Accident Hours (24H)"
              data={lineData}
              dataKey="value"
              xKey="time"
              height={270}
              isLoading={dashboardQuery.isLoading}
              emptyMessage="No confirmed accidents found for the current view."
              tooltipFormatter={(value) => [`${value} accidents`, "Volume"]}
              tooltipLabelFormatter={(label) => `${label}:00`}
            />

            {/*
              Accident Frequency by Location. The ramp itself (§2.2) lives in
              BarChartCard — this page only supplies the data and the
              full-name tooltip, since the Y-axis category is truncated for
              width but the hover target should not be.
            */}
            <BarChartCard
              title="Accident Frequency by Location"
              data={barData}
              dataKey="value"
              labelKey="name"
              height={340}
              isLoading={dashboardQuery.isLoading}
              emptyMessage="No location data available yet."
              tooltipFormatter={(value, _name, entry) => [
                `${value} accidents`,
                entry.payload?.fullName ?? entry.payload?.name,
              ]}
            />
          </div>

          {/* KPI cards column */}
          <div className="flex flex-col gap-5">
            <div className="h-[195px]">
              <StatCard
                elevated
                icon={RiRefreshLine}
                title="Ongoing Accidents"
                value={kpis?.ongoing ?? 0}
                isLoading={dashboardQuery.isLoading}
                subtext="Live incident queue"
              />
            </div>
            <div className="h-[195px]">
              <StatCard
                icon={RiCarLine}
                title="Total Accidents"
                value={kpis?.total_accidents ?? 0}
                isLoading={dashboardQuery.isLoading}
                subtext="Compared to last month"
              />
            </div>
            <div className="h-[195px]">
              <StatCard
                icon={RiCheckboxLine}
                title="Total Resolved"
                value={kpis?.total_resolved ?? 0}
                isLoading={dashboardQuery.isLoading}
                subtext="Compared to last month"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
