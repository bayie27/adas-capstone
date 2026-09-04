import { useState } from "react"
import { useRef, useEffect } from "react"
import { getAlerts } from "@/api/alerts"
import { createRetrainingExport, type RetrainingExportParams } from "@/api/exports"
import { useExportJobsStore } from "@/store/useExportJobsStore"
import { Modal } from "@/components/ui/Modal"
import { Button } from "@/components/ui/Button"
import type { ExportFormat } from "@/components/ui/ExportButton"
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
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeaderCell,
  TableRow,
  TableStateRow,
} from "@/components/ui/Table"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { useExportJobSubmit } from "@/hooks/useExportJobSubmit"
import { useAuthStore } from "@/store/useAuthStore"
import { formatPercent } from "@/utils/format"
import { getApiErrorMessage } from "@/api/client"
import { toast } from "@/store/useToastStore"
import { cn } from "@/utils/cn"
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
  const {
    page,
    pageSize,
    totalPages,
    offset,
    rangeStart,
    rangeEnd,
    next,
    prev,
    reset,
    goTo,
    setPageSize,
  } = usePagination(seenTotal, ITEMS_PER_PAGE)

  const performanceQuery = useQuery({
    queryKey: [
      ...PERFORMANCE_QUERY_KEY,
      debouncedSearchTerm,
      startDate,
      endDate,
      cameraId,
      pageSize,
      offset,
    ],
    queryFn: () =>
      getPerformanceAnalytics({
        search: debouncedSearchTerm || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        camera_id: cameraId ? [Number(cameraId)] : undefined,
        limit: pageSize,
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
    onSuccess: () => {
      toast.success("AI performance report downloaded successfully.")
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, "Failed to export AI performance report."))
    },
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
        status: ["Cleared", "Dismissed"],
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
      toast.success("Retraining dataset export job added to Export Jobs.")
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, "Failed to export retraining dataset."))
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
    toast.info("Preparing retraining dataset export...")
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

      <TableContainer
        footer={
          <PaginationFooter
            page={page}
            totalPages={totalPages}
            rangeStart={rangeStart}
            rangeEnd={rangeEndValue}
            totalFiltered={totalFiltered}
            pageSize={pageSize}
            isFetching={performanceQuery.isFetching}
            onPrev={prev}
            onNext={next}
            onPageChange={goTo}
            onPageSizeChange={setPageSize}
          />
        }
      >
        <Table>
          <TableHead>
            <TableHeaderCell>Camera Name</TableHeaderCell>
            <TableHeaderCell className="text-right">Accidents</TableHeaderCell>
            <TableHeaderCell className="text-right">Dismissed</TableHeaderCell>
            <TableHeaderCell className="text-right">Precision Score</TableHeaderCell>
            <TableHeaderCell className="text-right">Confidence Score</TableHeaderCell>
            <TableHeaderCell className="text-right">Dismissed Score</TableHeaderCell>
          </TableHead>
          <TableBody>
            {performanceQuery.isLoading ? (
              <TableStateRow colSpan={6}>Loading AI performance...</TableStateRow>
            ) : perCamera.length === 0 ? (
              <TableStateRow colSpan={6}>
                No camera statistics found for the current filters.
              </TableStateRow>
            ) : (
              perCamera.map((item) => (
                <TableRow key={item.camera_id}>
                  <TableCell className="font-medium text-fg">{item.camera_name}</TableCell>
                  <TableCell className="text-right text-fg-muted">{item.total_accidents}</TableCell>
                  <TableCell className="text-right text-fg-muted">{item.total_dismissed}</TableCell>
                  {/*
                    Same null-vs-value pattern as the two columns below:
                    `precision_score` is null (unmeasured), not 0, when
                    nothing has been acted on in the window. Rendering it as
                    a hardcoded danger colour regardless of null read as
                    "confirmed bad" rather than "nothing to measure yet" —
                    exactly the wrong claim to make silently on a capstone
                    metric.
                  */}
                  <TableCell
                    className={`text-right font-medium ${
                      item.precision_score === null ? "text-fg-muted" : "text-danger"
                    }`}
                  >
                    {formatPercent(item.precision_score)}
                  </TableCell>
                  <TableCell
                    className={cn(
                      "text-right font-medium",
                      item.avg_accident_confidence === null
                        ? "text-fg-muted"
                        : item.avg_accident_confidence * 100 >= 75
                          ? "text-fg"
                          : "text-danger",
                    )}
                  >
                    {formatPercent(item.avg_accident_confidence)}
                  </TableCell>
                  <TableCell
                    className={`text-right font-medium ${
                      item.avg_dismissed_confidence === null ? "text-fg-muted" : "text-danger"
                    }`}
                  >
                    {formatPercent(item.avg_dismissed_confidence)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Modal
        isOpen={showWarningModal}
        onClose={() => setShowWarningModal(false)}
        className="max-w-[512px]"
        hideClose
      >
        <div className="flex flex-col items-center pt-6 text-center">
          <div className="flex h-[58px] w-[58px] items-center justify-center relative overflow-hidden mb-4">
            <RiAlertLine size={44} className="text-warning z-10" />
          </div>
          <div className="flex flex-col items-center text-center w-full space-y-2 mb-4">
            <h3 className="text-lg font-semibold text-fg leading-[28px]">Dataset Too Small</h3>
            <div className="text-sm font-normal leading-[20px] text-fg-muted">
              {new Intl.NumberFormat("en-US").format(labelledCount ?? 0)} labelled incident
              {(labelledCount ?? 0) === 1 ? "" : "s"} in this range. Exporting fewer than 50 wastes
              a training run — widen the range or camera filter first.
            </div>
          </div>
          <div className="flex w-full items-center justify-end gap-2 mt-2">
            <Button variant="outline" size="md" onClick={() => setShowWarningModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" size="md" onClick={executeRetrainingExport}>
              Export Anyway
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
