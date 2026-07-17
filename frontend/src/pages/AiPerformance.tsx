import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import SearchLineIcon from "remixicon-react/SearchLineIcon"
import CalendarLineIcon from "remixicon-react/CalendarLineIcon"
import DownloadLineIcon from "remixicon-react/DownloadLineIcon"
import CarLineIcon from "remixicon-react/CarLineIcon"
import CloseCircleLineIcon from "remixicon-react/CloseCircleLineIcon"
import Focus3LineIcon from "remixicon-react/Focus3LineIcon"
import Dashboard3LineIcon from "remixicon-react/Dashboard3LineIcon"
import CameraLineIcon from "remixicon-react/CameraLineIcon"
import CloseLineIcon from "remixicon-react/CloseLineIcon"
import {
  exportPerformanceAnalyticsCsv,
  getPerformanceAnalytics,
} from "@/services/analytics"
import { PaginationFooter } from "@/components/ui/PaginationFooter"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { StatCard } from "@/components/ui/StatCard"
import { TableStateRow } from "@/components/ui/TableStateRow"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { formatPercent } from "@/utils/analytics"

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
  const perCamera = performanceQuery.data?.per_camera ?? []
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
        <h1 className="mb-0.5 text-xl font-semibold text-white">AI Performance</h1>
        <p className="text-xs text-[#737373]">
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
          icon={CarLineIcon}
          title="Total Accidents"
          value={performanceQuery.isLoading ? "..." : globalKpis?.total_accidents ?? 0}
          subtext="Confirmed accidents"
        />
        <StatCard
          icon={CloseCircleLineIcon}
          title="Total Dismissed"
          value={performanceQuery.isLoading ? "..." : globalKpis?.total_dismissed ?? 0}
          subtext="False positives"
        />
        <StatCard
          icon={Focus3LineIcon}
          title="Avg Precision Score"
          value={performanceQuery.isLoading ? "..." : formatPercent(globalKpis?.precision_score)}
          subtext="Confirmed / total acted alerts"
        />
        <StatCard
          icon={Dashboard3LineIcon}
          title="Avg Confidence Score"
          value={
            performanceQuery.isLoading ? "..." : formatPercent(globalKpis?.avg_accident_confidence)
          }
          subtext="Average accident confidence"
        />
        <StatCard
          icon={CloseCircleLineIcon}
          title="Avg Dismissed Score"
          value={
            performanceQuery.isLoading ? "..." : formatPercent(globalKpis?.avg_dismissed_confidence)
          }
          subtext="Average dismissed confidence"
        />
      </div>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative">
            <SearchLineIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#555]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(event) => {
                reset()
                setSearchTerm(event.target.value)
              }}
              placeholder="Search..."
              className="w-60 rounded-md border border-[#2A2A2A] bg-[#141414] py-1.5 pl-8 pr-4 text-xs text-white focus:border-[#52525B] focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1">
            <CalendarLineIcon size={13} className="text-[#737373]" />
            <input
              type="date"
              value={startDate}
              onChange={(e) => { reset(); setStartDate(e.target.value) }}
              className="bg-transparent text-xs text-[#D4D4D4] focus:outline-none [color-scheme:dark]"
            />
          </div>
          <span className="text-xs text-[#555]">to</span>
          <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1">
            <CalendarLineIcon size={13} className="text-[#737373]" />
            <input
              type="date"
              value={endDate}
              onChange={(e) => { reset(); setEndDate(e.target.value) }}
              className="bg-transparent text-xs text-[#D4D4D4] focus:outline-none [color-scheme:dark]"
            />
          </div>
            <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1">
              <CameraLineIcon size={13} className="text-[#737373]" />
              <select
                value={cameraId}
                onChange={(e) => { reset(); setCameraId(e.target.value) }}
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
          {hasDateFilter ? (
            <button
              type="button"
              onClick={() => { setStartDate(""); setEndDate(""); setCameraId(""); reset() }}
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
          className="flex items-center gap-2 rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <DownloadLineIcon size={13} />
          {exportMutation.isPending ? "Exporting..." : "Export"}
        </button>
      </div>

      {exportMutation.isError ? (
        <QueryErrorBanner error={exportMutation.error} fallback="Unable to export AI performance CSV." />
      ) : null}

      <div className="overflow-hidden rounded-xl border border-[#2A2A2A] bg-[#111111]">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#2A2A2A] bg-[#141414] text-[#737373]">
                <th className="px-6 py-4 text-xs font-medium">Camera Name</th>
                <th className="px-6 py-4 text-center text-xs font-medium">Accidents</th>
                <th className="px-6 py-4 text-center text-xs font-medium">Dismissed</th>
                <th className="px-6 py-4 text-center text-xs font-medium">Precision Score</th>
                <th className="px-6 py-4 text-center text-xs font-medium">Confidence Score</th>
                <th className="px-6 py-4 text-center text-xs font-medium">Dismissed Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2A2A2A]">
              {performanceQuery.isLoading ? (
                <TableStateRow colSpan={6}>Loading AI performance...</TableStateRow>
              ) : visibleRows.length === 0 ? (
                <TableStateRow colSpan={6}>
                  No camera statistics found for the current filters.
                </TableStateRow>
              ) : (
                visibleRows.map((item) => (
                  <tr key={item.camera_id} className="text-[#D4D4D4] transition-colors hover:bg-[#1A1A1A]">
                    <td className="px-6 py-4 text-xs font-medium">{item.camera_name}</td>
                    <td className="px-6 py-4 text-center text-xs">{item.total_accidents}</td>
                    <td className="px-6 py-4 text-center text-xs">{item.total_dismissed}</td>
                    <td className="px-6 py-4 text-center text-xs font-medium text-[#ef4444]">
                      {formatPercent(item.precision_score)}
                    </td>
                    <td
                      className={`px-6 py-4 text-center text-xs font-medium ${
                        item.avg_accident_confidence === null ? "text-[#737373]" : "text-emerald-500"
                      }`}
                    >
                      {formatPercent(item.avg_accident_confidence)}
                    </td>
                    <td
                      className={`px-6 py-4 text-center text-xs font-medium ${
                        item.avg_dismissed_confidence === null ? "text-[#737373]" : "text-[#ef4444]"
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
