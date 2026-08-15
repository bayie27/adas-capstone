import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { exportPerformanceAnalyticsCsv, getPerformanceAnalytics } from "@/api/analytics"
import { Button } from "@/components/ui/Button"
import { DateRangePicker } from "@/components/ui/DateRangePicker"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { PaginationFooter } from "@/components/ui/PaginationFooter"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { SearchInput } from "@/components/ui/SearchInput"
import { StatCard } from "@/components/ui/StatCard"
import { TableStateRow } from "@/components/ui/Table"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { formatPercent } from "@/utils/format"
import {
  RiCarLine,
  RiCloseCircleLine,
  RiCloseLine,
  RiDashboard3Line,
  RiDownloadLine,
  RiFocus3Line,
} from "@remixicon/react"

const PERFORMANCE_QUERY_KEY = ["performance-analytics"] as const
const ITEMS_PER_PAGE = 10

export default function AiPerformance() {
  const [searchTerm, setSearchTerm] = useState("")
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [cameraId, setCameraId] = useState("")
  const debouncedSearchTerm = useDebouncedValue(searchTerm.trim(), 300)

  const hasDateFilter = Boolean(startDate || endDate || cameraId)

  const camerasQuery = useCameraOptions()

  const cameraOptions = [
    { value: "", label: "All cameras" },
    ...(camerasQuery.data?.cameras ?? []).map((c) => ({
      value: String(c.camera_id),
      label: c.camera_name,
    })),
  ]

  const performanceQuery = useQuery({
    queryKey: [...PERFORMANCE_QUERY_KEY, debouncedSearchTerm, startDate, endDate, cameraId],
    queryFn: () =>
      getPerformanceAnalytics({
        search: debouncedSearchTerm || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        camera_id: cameraId ? [Number(cameraId)] : undefined,
      }),
    placeholderData: (previousData) => previousData,
  })

  const exportMutation = useMutation({
    mutationFn: () =>
      exportPerformanceAnalyticsCsv({
        search: debouncedSearchTerm || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        camera_id: cameraId ? [Number(cameraId)] : undefined,
      }),
  })

  const globalKpis = performanceQuery.data?.global_kpis
  const perCamera = useMemo(() => performanceQuery.data?.per_camera ?? [], [performanceQuery.data])
  // Client-side pagination: the total is `perCamera.length`, available in the
  // same render, so usePagination clamps the page directly (no state mirror).
  const { page, totalPages, offset, rangeStart, rangeEnd, next, prev, reset } = usePagination(
    perCamera.length,
    ITEMS_PER_PAGE,
  )

  const visibleRows = useMemo(
    () => perCamera.slice(offset, offset + ITEMS_PER_PAGE),
    [perCamera, offset],
  )

  const rangeEndValue = rangeEnd(visibleRows.length)

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-fg">AI Performance</h1>
        <p className="text-xs text-fg-muted">
          Analyze confidence levels and track overall detection accuracy of cameras
        </p>
      </div>

      {performanceQuery.isError ? (
        <QueryErrorBanner
          error={performanceQuery.error}
          fallback="Unable to load AI performance analytics."
          onRetry={() => performanceQuery.refetch()}
        />
      ) : null}

      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-5">
        <StatCard
          elevated
          icon={RiCarLine}
          title="Total Accidents"
          value={globalKpis?.total_accidents ?? 0}
          isLoading={performanceQuery.isLoading}
          subtext="Confirmed accidents"
        />
        <StatCard
          icon={RiCloseCircleLine}
          title="Total Dismissed"
          value={globalKpis?.total_dismissed ?? 0}
          isLoading={performanceQuery.isLoading}
          subtext="False positives"
        />
        <StatCard
          icon={RiFocus3Line}
          title="Avg Precision Score"
          value={formatPercent(globalKpis?.precision_score)}
          isLoading={performanceQuery.isLoading}
          subtext="Confirmed / total acted alerts"
        />
        {/*
          The frame's fourth KPI is "Avg Confidence Score", but
          PerformanceGlobalKpis has no combined average — only a separate
          accident-confidence and dismissed-confidence figure. Rendered as
          accident confidence and labelled accordingly rather than averaging
          the two client-side, which would be a number the backend never
          computed.
        */}
        <StatCard
          icon={RiDashboard3Line}
          title="Avg Accident Confidence"
          value={formatPercent(globalKpis?.avg_accident_confidence)}
          isLoading={performanceQuery.isLoading}
          subtext="Average accident confidence"
        />
        <StatCard
          icon={RiCloseCircleLine}
          title="Avg Dismissed Score"
          value={formatPercent(globalKpis?.avg_dismissed_confidence)}
          isLoading={performanceQuery.isLoading}
          subtext="Average dismissed confidence"
        />
      </div>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <SearchInput
            value={searchTerm}
            onChange={(value) => {
              reset()
              setSearchTerm(value)
            }}
            placeholder="Search..."
          />
          <DateRangePicker
            start={startDate}
            end={endDate}
            onStartChange={(value) => {
              reset()
              setStartDate(value)
            }}
            onEndChange={(value) => {
              reset()
              setEndDate(value)
            }}
            label="Filter performance by date"
          />
          <FilterSelect
            value={cameraId}
            options={cameraOptions}
            onChange={(value) => {
              reset()
              setCameraId(value)
            }}
          />
          {hasDateFilter ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setStartDate("")
                setEndDate("")
                setCameraId("")
                reset()
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
          className="flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-fg-on-primary transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RiDownloadLine size={13} />
          {exportMutation.isPending ? "Exporting..." : "Export"}
        </button>
      </div>

      {exportMutation.isError ? (
        <QueryErrorBanner
          error={exportMutation.error}
          fallback="Unable to export AI performance CSV."
        />
      ) : null}

      <div className="overflow-hidden rounded-xl border border-stroke bg-surface-1">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-stroke bg-surface-1 text-fg-muted">
                <th className="px-6 py-4 text-xs font-medium">Camera Name</th>
                <th className="px-6 py-4 text-right text-xs font-medium">Accidents</th>
                <th className="px-6 py-4 text-right text-xs font-medium">Dismissed</th>
                <th className="px-6 py-4 text-right text-xs font-medium">Precision Score</th>
                <th className="px-6 py-4 text-right text-xs font-medium">Confidence Score</th>
                <th className="px-6 py-4 text-right text-xs font-medium">Dismissed Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stroke">
              {performanceQuery.isLoading ? (
                <TableStateRow colSpan={6}>Loading AI performance...</TableStateRow>
              ) : visibleRows.length === 0 ? (
                <TableStateRow colSpan={6}>
                  No camera statistics found for the current filters.
                </TableStateRow>
              ) : (
                visibleRows.map((item) => (
                  <tr
                    key={item.camera_id}
                    className="text-fg-body transition-colors hover:bg-surface-1"
                  >
                    <td className="px-6 py-4 text-xs font-medium">{item.camera_name}</td>
                    <td className="px-6 py-4 text-right text-xs">{item.total_accidents}</td>
                    <td className="px-6 py-4 text-right text-xs">{item.total_dismissed}</td>
                    {/*
                      Same null-vs-value pattern as the two columns below:
                      `precision_score` is null (unmeasured), not 0, when
                      nothing has been acted on in the window. Rendering it as
                      a hardcoded danger colour regardless of null read as
                      "confirmed bad" rather than "nothing to measure yet" —
                      exactly the wrong claim to make silently on a capstone
                      metric.
                    */}
                    <td
                      className={`px-6 py-4 text-right text-xs font-medium ${
                        item.precision_score === null ? "text-fg-muted" : "text-danger"
                      }`}
                    >
                      {formatPercent(item.precision_score)}
                    </td>
                    <td
                      className={`px-6 py-4 text-right text-xs font-medium ${
                        item.avg_accident_confidence === null ? "text-fg-muted" : "text-success"
                      }`}
                    >
                      {formatPercent(item.avg_accident_confidence)}
                    </td>
                    <td
                      className={`px-6 py-4 text-right text-xs font-medium ${
                        item.avg_dismissed_confidence === null ? "text-fg-muted" : "text-danger"
                      }`}
                    >
                      {formatPercent(item.avg_dismissed_confidence)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <PaginationFooter
          page={page}
          totalPages={totalPages}
          rangeStart={rangeStart}
          rangeEnd={rangeEndValue}
          totalFiltered={perCamera.length}
          pageSize={ITEMS_PER_PAGE}
          isFetching={performanceQuery.isFetching}
          onPrev={prev}
          onNext={next}
        />
      </div>
    </div>
  )
}
