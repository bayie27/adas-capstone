import { useState } from "react"
import { useRef, useEffect } from "react"
import { getAlerts } from "@/api/alerts"
import { createRetrainingExport, type RetrainingExportParams } from "@/api/exports"
import { useExportJobsStore } from "@/store/useExportJobsStore"
import { Modal } from "@/components/ui/Modal"
import { Button } from "@/components/ui/Button"
import { RiArrowDownSLine, RiDownloadLine, RiAlertLine } from "@remixicon/react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { exportPerformanceAnalytics, getPerformanceAnalytics } from "@/api/analytics"
import { ClearFiltersButton } from "@/components/ui/ClearFiltersButton"
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
import { useExportJobSubmit } from "@/hooks/useExportJobSubmit"
import { useAuthStore } from "@/store/useAuthStore"
import { formatPercent } from "@/utils/format"
import { RiCarLine, RiCloseCircleLine, RiDashboard3Line, RiFocus3Line } from "@remixicon/react"

const PERFORMANCE_QUERY_KEY = ["performance-analytics"] as const
const ITEMS_PER_PAGE = 10

export default function AiPerformance() {
  const role = useAuthStore((state) => state.role)
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

  // See Users.tsx: mirror the query total into state so usePagination can clamp
  // the page at read time without an effect.
  const [seenTotal, setSeenTotal] = useState(0)
  const { page, totalPages, offset, rangeStart, rangeEnd, next, prev, reset } = usePagination(
    seenTotal,
    ITEMS_PER_PAGE,
  )

  const performanceQuery = useQuery({
    queryKey: [...PERFORMANCE_QUERY_KEY, debouncedSearchTerm, startDate, endDate, cameraId, offset],
    queryFn: () =>
      getPerformanceAnalytics({
        search: debouncedSearchTerm || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        camera_id: cameraId ? [Number(cameraId)] : undefined,
        limit: ITEMS_PER_PAGE,
        offset,
      }),
    placeholderData: (previousData) => previousData,
  })

  const exportMutation = useMutation({
    mutationFn: (format: ExportFormat) =>
      exportPerformanceAnalytics(
        {
          search: debouncedSearchTerm || undefined,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          camera_id: cameraId ? [Number(cameraId)] : undefined,
        },
        format,
      ),
  })

  const exportJobMutation = useExportJobSubmit()

  const [showWarningModal, setShowWarningModal] = useState(false)
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false)
  const menuContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isExportMenuOpen) return
    const handleClick = (e: MouseEvent) => {
      if (!menuContainerRef.current?.contains(e.target as Node)) {
        setIsExportMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [isExportMenuOpen])

  const track = useExportJobsStore((state) => state.track)

  const labelledCountQuery = useQuery({
    queryKey: ["retraining-labelled-count", startDate, endDate, cameraId],
    queryFn: () =>
      getAlerts({
        status: ["Resolved", "Dismissed"],
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        camera_id: cameraId ? [Number(cameraId)] : undefined,
        limit: 1,
      }),
  })
  const labelledCount = labelledCountQuery.data?.total_filtered

  const retrainingJobMutation = useMutation({
    mutationFn: (params: RetrainingExportParams) => createRetrainingExport(params),
    onSuccess: (response) => {
      track({
        jobId: response.job_id,
        reportType: "retraining",
        format: "zip",
        createdAt: new Date().toISOString(),
      })
    },
  })

  function handleRetrainingExportClick() {
    setIsExportMenuOpen(false)
    if (labelledCount !== undefined && labelledCount < 50) {
      setShowWarningModal(true)
    } else {
      executeRetrainingExport()
    }
  }

  function executeRetrainingExport() {
    setShowWarningModal(false)
    retrainingJobMutation.mutate({
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      camera_id: cameraId ? [Number(cameraId)] : undefined,
    })
  }

  const globalKpis = performanceQuery.data?.global_kpis
  const perCamera = performanceQuery.data?.per_camera ?? []
  const totalFiltered = performanceQuery.data?.total_filtered ?? 0
  if (totalFiltered !== seenTotal) {
    setSeenTotal(totalFiltered)
  }
  const rangeEndValue = rangeEnd(perCamera.length)

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
            <ClearFiltersButton
              onClick={() => {
                setStartDate("")
                setEndDate("")
                setCameraId("")
                reset()
              }}
            />
          ) : null}
        </div>
        {/*
          total_filtered (P19 §4), not perCamera.length — the page now only
          holds one page of rows (default 10), and the export pre-flight
          needs the real filtered count across every page, not just the one
          currently on screen.
        */}

        <div className="relative" ref={menuContainerRef}>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsExportMenuOpen(!isExportMenuOpen)}
            isLoading={
              exportMutation.isPending ||
              exportJobMutation.isPending ||
              retrainingJobMutation.isPending
            }
            loadingLabel="Exporting..."
          >
            <RiDownloadLine size={13} />
            Export
            <RiArrowDownSLine size={14} />
          </Button>

          {isExportMenuOpen && (
            <div className="absolute right-0 top-full mt-1 z-50 w-64 rounded-md border border-stroke bg-surface-1 py-1 shadow-overlay">
              <div className="px-3 py-1.5 text-xs font-semibold text-fg-muted">
                Performance Report
              </div>
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-xs text-fg-body hover:bg-surface-2"
                onClick={() => {
                  setIsExportMenuOpen(false)
                  exportMutation.mutate("csv")
                }}
              >
                Export as CSV
              </button>
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-xs text-fg-body hover:bg-surface-2"
                onClick={() => {
                  setIsExportMenuOpen(false)
                  exportMutation.mutate("pdf")
                }}
              >
                Export as PDF
              </button>

              {role === "Admin" && (
                <>
                  <div className="my-1 border-t border-stroke" />
                  <div className="px-3 py-1.5 text-xs font-semibold text-fg-muted">
                    Training Data
                  </div>
                  <button
                    type="button"
                    className="w-full px-3 py-2 text-left text-xs text-fg-body hover:bg-surface-2"
                    onClick={handleRetrainingExportClick}
                  >
                    Export Retraining Dataset (ZIP)
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {exportMutation.isError ? (
        <QueryErrorBanner
          error={exportMutation.error}
          fallback="Unable to export the AI performance report."
        />
      ) : null}

      {exportJobMutation.isError ? (
        <QueryErrorBanner
          error={exportJobMutation.error}
          fallback="Unable to start the background export job."
        />
      ) : null}

      {retrainingJobMutation.isError ? (
        <QueryErrorBanner
          error={retrainingJobMutation.error}
          fallback="Unable to start the retraining export job."
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
              ) : perCamera.length === 0 ? (
                <TableStateRow colSpan={6}>
                  No camera statistics found for the current filters.
                </TableStateRow>
              ) : (
                perCamera.map((item) => (
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
          totalFiltered={totalFiltered}
          pageSize={ITEMS_PER_PAGE}
          isFetching={performanceQuery.isFetching}
          onPrev={prev}
          onNext={next}
        />
      </div>

      <Modal isOpen={showWarningModal} onClose={() => setShowWarningModal(false)}>
        <div className="flex flex-col items-center gap-4 text-center">
          <RiAlertLine size={48} className="text-warning" />
          <div className="space-y-2">
            <h3 className="text-lg font-semibold text-fg">Dataset Too Small</h3>
            <p className="text-sm font-normal leading-relaxed text-fg-muted">
              {new Intl.NumberFormat("en-US").format(labelledCount ?? 0)} labelled incident
              {(labelledCount ?? 0) === 1 ? "" : "s"} in this range. Exporting fewer than 50 wastes
              a training run — widen the range or camera filter first.
            </p>
          </div>
        </div>
        <div className="flex w-full justify-end gap-2 mt-4">
          <Button variant="outline" onClick={() => setShowWarningModal(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={executeRetrainingExport}>
            Export Anyway
          </Button>
        </div>
      </Modal>
    </div>
  )
}
