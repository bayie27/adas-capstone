import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { exportDashboardAnalytics, getDashboardAnalytics } from "@/api/analytics"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { useExportJobSubmit } from "@/hooks/useExportJobSubmit"
import { AreaChartCard } from "@/components/charts/AreaChartCard"
import { BarChartCard } from "@/components/charts/BarChartCard"
import { ClearFiltersButton } from "@/components/ui/ClearFiltersButton"
import { DateRangePicker } from "@/components/ui/DateRangePicker"
import { ExportButton, type ExportFormat } from "@/components/ui/ExportButton"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { StatCard } from "@/components/ui/StatCard"
import {
  daysBetweenInclusive,
  getLastSevenDaysRange,
  toPhilippineDayEnd,
  toPhilippineDayStart,
} from "@/utils/dateRange"
import { formatHourLabel, truncateLabel } from "@/utils/format"
import type { AnalyticsFilters } from "@/api/analytics"
import { RiCarLine, RiCheckboxLine, RiRefreshLine } from "@remixicon/react"

/**
 * `null` means no previous window to compare against (all-time load,
 * half-open range, or a previous window that was itself zero) -- never
 * render null as "0%", they're different facts. A real zero renders as a
 * neutral "0%", not success or danger.
 */
function formatDeltaText(value: number): string {
  if (value === 0) return "0%"
  const sign = value > 0 ? "+" : "−"
  return `${sign}${Math.abs(value).toFixed(1)}%`
}

/**
 * Sign does not map to colour uniformly across these three KPIs -- more
 * accidents and more still-ongoing incidents are both a *positive* delta
 * that reads as bad news; only "more cleared" is a positive delta that's
 * actually good. `worseWhenPositive` lets one function express both
 * mappings instead of inlining the flip at each call site.
 */
function deltaTone(value: number, worseWhenPositive: boolean): boolean | null {
  if (value === 0) return null
  const isGood = worseWhenPositive ? value < 0 : value > 0
  return isGood
}

/**
 * What a KPI's delta chip is actually comparing against, e.g. "Compared to
 * the previous 7 days" -- the backend compares to the immediately
 * preceding window of the *same* length as whatever's selected
 * (`_previous_window()`, analytics.py), which is not always 7 days once an
 * operator picks a custom range, so this is derived from the live
 * selection rather than a fixed string. Spelled out in full, no "vs"
 * shorthand, to match this app's existing caption voice (e.g.
 * `describeCameraDesiredState`'s "Held for an open incident").
 */
function formatDeltaCaption(days: number): string {
  return `Compared to the previous ${days} day${days === 1 ? "" : "s"}`
}

/**
 * Stacks a KPI's own description (if any) over its delta caption (if a
 * comparison window applies) into one subtext block -- `undefined` when
 * neither is present, so `StatCard` still omits the row entirely rather
 * than rendering an empty one.
 */
function renderKpiSubtext(description: string | undefined, deltaCaption: string | undefined) {
  if (!description && !deltaCaption) return undefined
  return (
    <div className="flex flex-col gap-0.5">
      {description ? <div>{description}</div> : null}
      {deltaCaption ? <div>{deltaCaption}</div> : null}
    </div>
  )
}

export default function Dashboard() {
  // Trends are what this screen is for -- a fresh load defaults to the last
  // 7 days rather than an unbounded all-time query. Seeded from one
  // lazily-initialized range so both fields agree even if the initializers
  // ran a millisecond apart across a day boundary.
  const [defaultRange] = useState(() => getLastSevenDaysRange())
  const [startDate, setStartDate] = useState(defaultRange.start)
  const [endDate, setEndDate] = useState(defaultRange.end)
  const [cameraId, setCameraId] = useState("")

  const filters: AnalyticsFilters = {
    start_date: toPhilippineDayStart(startDate),
    end_date: toPhilippineDayEnd(endDate),
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
    mutationFn: (format: ExportFormat) => exportDashboardAnalytics(filters, format),
  })

  const exportJobMutation = useExportJobSubmit()

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

  // Both dates present is exactly the condition under which the backend's
  // own _previous_window() returns a comparison window (see its
  // start_date/end_date None check) -- an absent bound means "all time",
  // which has no previous period to name.
  const comparisonDays = startDate && endDate ? daysBetweenInclusive(startDate, endDate) : null

  return (
    <div className="mx-auto max-w-[1400px] p-8">
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
            <ClearFiltersButton
              onClick={() => {
                setStartDate("")
                setEndDate("")
                setCameraId("")
              }}
            />
          ) : null}
        </div>
        {/*
            This screen cannot supply a pre-flight row count — the dashboard
            endpoint returns aggregates, not a filtered row count — so
            `rowCount` is left undefined and ExportButton renders no
            pre-flight. An unknown count must never render as an all-clear;
            the 413 handler below still applies, since the export route
            counts the underlying rows regardless.
          */}
        <ExportButton
          isExporting={exportMutation.isPending}
          exportHasError={exportMutation.isError}
          onExport={(format) => exportMutation.mutate(format)}
          isSubmittingJob={exportJobMutation.isPending}
          onExportJob={(format) =>
            exportJobMutation.mutateAsync({
              report_type: "dashboard",
              format,
              start_date: filters.start_date,
              end_date: filters.end_date,
              camera_id: filters.camera_id,
            })
          }
        />
      </div>

      {exportMutation.isError ? (
        <QueryErrorBanner
          error={exportMutation.error}
          fallback="Unable to export the dashboard report."
        />
      ) : null}

      {exportJobMutation.isError ? (
        <QueryErrorBanner
          error={exportJobMutation.error}
          fallback="Unable to start the background export job."
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
              subtext={renderKpiSubtext(
                "Live incident queue",
                kpis?.ongoing_delta_pct != null && comparisonDays != null
                  ? formatDeltaCaption(comparisonDays)
                  : undefined,
              )}
              delta={
                kpis?.ongoing_delta_pct != null
                  ? formatDeltaText(kpis.ongoing_delta_pct)
                  : undefined
              }
              deltaPositive={
                kpis?.ongoing_delta_pct != null
                  ? deltaTone(kpis.ongoing_delta_pct, true)
                  : undefined
              }
            />
          </div>
          <div className="h-[195px]">
            <StatCard
              icon={RiCarLine}
              title="Total Accidents"
              value={kpis?.total_accidents ?? 0}
              isLoading={dashboardQuery.isLoading}
              subtext={renderKpiSubtext(
                undefined,
                kpis?.total_accidents_delta_pct != null && comparisonDays != null
                  ? formatDeltaCaption(comparisonDays)
                  : undefined,
              )}
              delta={
                kpis?.total_accidents_delta_pct != null
                  ? formatDeltaText(kpis.total_accidents_delta_pct)
                  : undefined
              }
              deltaPositive={
                kpis?.total_accidents_delta_pct != null
                  ? deltaTone(kpis.total_accidents_delta_pct, true)
                  : undefined
              }
            />
          </div>
          <div className="h-[195px]">
            <StatCard
              icon={RiCheckboxLine}
              title="Total Cleared"
              value={kpis?.total_cleared ?? 0}
              isLoading={dashboardQuery.isLoading}
              subtext={renderKpiSubtext(
                undefined,
                kpis?.total_cleared_delta_pct != null && comparisonDays != null
                  ? formatDeltaCaption(comparisonDays)
                  : undefined,
              )}
              delta={
                kpis?.total_cleared_delta_pct != null
                  ? formatDeltaText(kpis.total_cleared_delta_pct)
                  : undefined
              }
              deltaPositive={
                kpis?.total_cleared_delta_pct != null
                  ? deltaTone(kpis.total_cleared_delta_pct, false)
                  : undefined
              }
            />
          </div>
        </div>
      </div>
    </div>
  )
}
