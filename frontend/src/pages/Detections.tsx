import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { DateRangePicker } from "@/components/ui/DateRangePicker"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { Modal } from "@/components/ui/Modal"
import { PaginationFooter } from "@/components/ui/PaginationFooter"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { SearchInput } from "@/components/ui/SearchInput"
import { SnapshotImage } from "@/components/ui/SnapshotImage"
import { AlertStatusText } from "@/components/ui/StatusText"
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
import { Tabs } from "@/components/ui/Tabs"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import {
  confirmAlert,
  dismissAlert,
  exportAlerts,
  getAlertDetails,
  getAlerts,
  resolveAlert,
} from "@/api/alerts"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { useUserOptions } from "@/hooks/useUserOptions"
import { useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
import type { AlertLog, AlertStatus } from "@/api/alerts"
import {
  formatAlertCode,
  formatAlertConfidence,
  getAlertBadgeClass,
  getAlertBorderClass,
  getAlertLastHandledBy,
  getAlertLastUpdated,
} from "@/utils/format"
import { getApiErrorMessage } from "@/api/client"
import { formatFullDateTime } from "@/utils/datetime"
import { cn } from "@/utils/cn"
import { RiCloseLine, RiDownloadLine, RiEyeLine } from "@remixicon/react"

const ALERTS_PAGE_SIZE = 10
const ACTIVE_ALERT_STATUSES: AlertStatus[] = ["Unverified", "Ongoing"]
const LOG_ALERT_STATUSES: AlertStatus[] = ["Dismissed", "Resolved"]

type TabKey = "ongoing" | "logs"

const TAB_ITEMS = [
  { value: "ongoing" as const, label: "Ongoing" },
  { value: "logs" as const, label: "Logs" },
]

export default function Detections() {
  const queryClient = useQueryClient()
  const removeAlert = useAlertStore((state) => state.removeAlert)
  const [activeTab, setActiveTab] = useState<TabKey>("ongoing")
  const [logSearch, setLogSearch] = useState("")
  const debouncedLogSearch = useDebouncedValue(logSearch.trim(), 300)
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [cameraId, setCameraId] = useState("")
  const [userId, setUserId] = useState("")

  const role = useAuthStore((state) => state.role)
  const hasFilters = Boolean(startDate || endDate || cameraId || userId)

  const camerasQuery = useCameraOptions()

  const usersQuery = useUserOptions({ enabled: role === "Admin" })
  const [selectedAlertId, setSelectedAlertId] = useState<number | null>(null)
  const [selectedAlertPreview, setSelectedAlertPreview] = useState<AlertLog | null>(null)

  // Two independent paginations (one per tab). See Users.tsx for why the total
  // is mirrored into state and synced during render.
  const [seenActiveTotal, setSeenActiveTotal] = useState(0)
  const activePagination = usePagination(seenActiveTotal, ALERTS_PAGE_SIZE)
  const [seenLogsTotal, setSeenLogsTotal] = useState(0)
  const logsPagination = usePagination(seenLogsTotal, ALERTS_PAGE_SIZE)

  const activeAlertsQuery = useQuery({
    queryKey: ["alerts", "active", activePagination.offset],
    queryFn: () =>
      getAlerts({
        status: ACTIVE_ALERT_STATUSES,
        limit: ALERTS_PAGE_SIZE,
        offset: activePagination.offset,
      }),
    placeholderData: (previousData) => previousData,
  })

  const logsQuery = useQuery({
    queryKey: [
      "alerts",
      "logs",
      debouncedLogSearch,
      logsPagination.offset,
      startDate,
      endDate,
      cameraId,
      userId,
    ],
    queryFn: () =>
      getAlerts({
        status: LOG_ALERT_STATUSES,
        search: debouncedLogSearch || undefined,
        limit: ALERTS_PAGE_SIZE,
        offset: logsPagination.offset,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        camera_id: cameraId ? [Number(cameraId)] : undefined,
        user_id: userId ? [Number(userId)] : undefined,
      }),
    placeholderData: (previousData) => previousData,
  })

  const alertDetailsQuery = useQuery({
    queryKey: ["alert-details", selectedAlertId],
    queryFn: () => getAlertDetails(selectedAlertId as number),
    enabled: selectedAlertId !== null,
  })

  const exportMutation = useMutation({
    mutationFn: () =>
      exportAlerts({
        status: LOG_ALERT_STATUSES,
        search: debouncedLogSearch || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        camera_id: cameraId ? [Number(cameraId)] : undefined,
        user_id: userId ? [Number(userId)] : undefined,
      }),
  })

  const handleMutationSuccess = (updatedAlert: AlertLog) => {
    queryClient.setQueryData(["alert-details", updatedAlert.log_id], updatedAlert)
    setSelectedAlertPreview(updatedAlert)
    removeAlert(updatedAlert.log_id)
    queryClient.invalidateQueries({ queryKey: ["alerts"] })
  }

  const confirmMutation = useMutation({
    mutationFn: confirmAlert,
    onSuccess: handleMutationSuccess,
  })

  const dismissMutation = useMutation({
    mutationFn: dismissAlert,
    onSuccess: handleMutationSuccess,
  })

  const resolveMutation = useMutation({
    mutationFn: resolveAlert,
    onSuccess: handleMutationSuccess,
  })

  const activeTotal = activeAlertsQuery.data?.total_filtered ?? 0
  if (activeTotal !== seenActiveTotal) {
    setSeenActiveTotal(activeTotal)
  }
  const logsTotal = logsQuery.data?.total_filtered ?? 0
  if (logsTotal !== seenLogsTotal) {
    setSeenLogsTotal(logsTotal)
  }

  const currentQuery = activeTab === "ongoing" ? activeAlertsQuery : logsQuery
  const currentPagination = activeTab === "ongoing" ? activePagination : logsPagination

  // Render rows in the server's order. The server paginates (limit/offset), so
  // it defines the total order; re-sorting a single page by a different key
  // would make page boundaries and visible order disagree.
  const currentRows = currentQuery.data?.logs ?? []

  const currentTotalFiltered = currentQuery.data?.total_filtered ?? 0
  const rangeStart = currentPagination.rangeStart
  const rangeEndValue = currentPagination.rangeEnd(currentRows.length)

  const selectedAlert = alertDetailsQuery.data ?? selectedAlertPreview

  const isTransitionPending =
    confirmMutation.isPending || dismissMutation.isPending || resolveMutation.isPending

  const transitionError = useMemo(() => {
    const firstError =
      confirmMutation.error ?? dismissMutation.error ?? resolveMutation.error ?? null

    return firstError ? getApiErrorMessage(firstError, "Unable to update alert status.") : null
  }, [confirmMutation.error, dismissMutation.error, resolveMutation.error])

  const closeModal = () => {
    setSelectedAlertId(null)
    setSelectedAlertPreview(null)
    confirmMutation.reset()
    dismissMutation.reset()
    resolveMutation.reset()
  }

  const openAlertModal = (alert: AlertLog) => {
    setSelectedAlertPreview(alert)
    setSelectedAlertId(alert.log_id)
    confirmMutation.reset()
    dismissMutation.reset()
    resolveMutation.reset()
  }

  const closedTimeLabel =
    selectedAlert?.detection_status === "Resolved" ? "TIME RESOLVED" : "TIME CLOSED"

  const cameraOptions = [
    { value: "", label: "All cameras" },
    ...(camerasQuery.data?.cameras ?? []).map((c) => ({
      value: String(c.camera_id),
      label: c.camera_name,
    })),
  ]

  const userOptions = [
    { value: "", label: "All operators" },
    ...(usersQuery.data?.users ?? []).map((u) => ({
      value: String(u.user_id),
      label: u.first_name && u.last_name ? `${u.first_name} ${u.last_name}` : u.username,
    })),
  ]

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        {/*
          text-xl / text-xs matches Cameras and Users as shipped, not §2.4's
          H3 (24px). Phase 6 set that precedent and it is merged; a Detections
          title two sizes larger than the screen beside it reads as a bug, so
          the deviation is carried rather than half-corrected here. Fixing all
          nine page titles at once is a separate, mechanical change.
        */}
        <h1 className="mb-0.5 text-xl font-semibold text-fg">Detections</h1>
        <p className="text-xs text-fg-muted">
          Monitor ongoing AI detections and review historical logs to verify reported incidents
        </p>
      </div>

      <div className="mb-6">
        <Tabs
          items={TAB_ITEMS}
          value={activeTab}
          onChange={setActiveTab}
          variant="chip"
          label="Detections view"
        />
      </div>

      {/*
        The Ongoing tab draws no toolbar (37:76) — it is a live queue, not a
        filterable archive, and the two chips below are read-only statements of
        what the tab contains. Only the Logs tab (112:8438) gets search, a date
        range, the dropdowns and Export.
      */}
      {activeTab === "logs" ? (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <SearchInput
              value={logSearch}
              onChange={(value) => {
                logsPagination.reset()
                setLogSearch(value)
              }}
              placeholder="Search accident no. or camera..."
            />
            <DateRangePicker
              start={startDate}
              end={endDate}
              onStartChange={(value) => {
                logsPagination.reset()
                setStartDate(value)
              }}
              onEndChange={(value) => {
                logsPagination.reset()
                setEndDate(value)
              }}
              label="Filter incidents by date"
            />
            <FilterSelect
              value={cameraId}
              options={cameraOptions}
              onChange={(value) => {
                logsPagination.reset()
                setCameraId(value)
              }}
            />
            {role === "Admin" ? (
              <FilterSelect
                value={userId}
                options={userOptions}
                onChange={(value) => {
                  logsPagination.reset()
                  setUserId(value)
                }}
              />
            ) : null}
            {hasFilters ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setStartDate("")
                  setEndDate("")
                  setCameraId("")
                  setUserId("")
                  logsPagination.reset()
                }}
              >
                <RiCloseLine size={13} />
                Clear
              </Button>
            ) : null}
          </div>
          <Button
            variant="primary"
            size="sm"
            isLoading={exportMutation.isPending}
            loadingLabel="Exporting…"
            onClick={() => exportMutation.mutate()}
          >
            <RiDownloadLine size={13} />
            Export
          </Button>
        </div>
      ) : (
        <div className="mb-6 flex flex-wrap items-center gap-2.5">
          <span className="rounded-md border border-stroke bg-surface-1 px-3 py-1.5 text-caption text-fg-body">
            Unverified &amp; Ongoing
          </span>
          <span className="rounded-md border border-stroke bg-surface-1 px-3 py-1.5 text-caption text-fg-body">
            Live queue
          </span>
        </div>
      )}

      {activeTab === "logs" && exportMutation.isError ? (
        <QueryErrorBanner error={exportMutation.error} fallback="Unable to export logs." />
      ) : null}

      {currentQuery.isError ? (
        <QueryErrorBanner
          error={currentQuery.error}
          fallback={
            activeTab === "ongoing"
              ? "Unable to load active alerts."
              : "Unable to load historical logs."
          }
          onRetry={() => currentQuery.refetch()}
        />
      ) : null}

      <TableContainer
        footer={
          <PaginationFooter
            page={currentPagination.page}
            totalPages={currentPagination.totalPages}
            rangeStart={rangeStart}
            rangeEnd={rangeEndValue}
            totalFiltered={currentTotalFiltered}
            pageSize={ALERTS_PAGE_SIZE}
            isFetching={currentQuery.isFetching}
            onPrev={currentPagination.prev}
            onNext={currentPagination.next}
            onPageChange={currentPagination.goTo}
          />
        }
      >
        <Table>
          <TableHead>
            <TableHeaderCell>Accident No.</TableHeaderCell>
            <TableHeaderCell>Timestamp</TableHeaderCell>
            <TableHeaderCell>Camera Name</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Last Handled By</TableHeaderCell>
            <TableHeaderCell>Last Updated</TableHeaderCell>
            <TableHeaderCell className="text-right">Actions</TableHeaderCell>
          </TableHead>
          <TableBody>
            {currentQuery.isLoading ? (
              <TableStateRow colSpan={7}>
                {activeTab === "ongoing" ? "Loading active alerts…" : "Loading logs…"}
              </TableStateRow>
            ) : currentRows.length === 0 ? (
              <TableStateRow colSpan={7}>
                {activeTab === "ongoing"
                  ? "No active alerts in the queue."
                  : "No historical logs found for the current filters."}
              </TableStateRow>
            ) : (
              currentRows.map((item) => (
                <TableRow key={item.log_id}>
                  <TableCell className="font-medium text-fg">
                    {formatAlertCode(item.log_id)}
                  </TableCell>
                  <TableCell className="text-fg-muted">
                    {formatFullDateTime(item.detected_at)}
                  </TableCell>
                  <TableCell>{item.camera_name ?? "Unknown Camera"}</TableCell>
                  <TableCell>
                    <AlertStatusText status={item.detection_status} />
                  </TableCell>
                  <TableCell className="text-fg-muted">{getAlertLastHandledBy(item)}</TableCell>
                  <TableCell className="text-fg-muted">{getAlertLastUpdated(item)}</TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end">
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 w-7 px-0"
                        aria-label={`View ${formatAlertCode(item.log_id)}`}
                        onClick={() => openAlertModal(item)}
                      >
                        <RiEyeLine size={14} />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Modal
        isOpen={selectedAlertId !== null}
        onClose={closeModal}
        hideClose
        className={cn(
          "max-w-lg overflow-hidden border-t-4 p-0",
          selectedAlert ? getAlertBorderClass(selectedAlert.detection_status) : "border-t-fg",
        )}
      >
        <div className="flex flex-col bg-surface-2">
          <div className="flex items-center justify-between border-b border-border px-6 py-4">
            <h2 className="text-caption font-semibold uppercase tracking-[0.08em] text-fg">
              ACCIDENT DETAILS
            </h2>
            <button
              type="button"
              onClick={closeModal}
              className="text-fg-muted transition-colors hover:text-fg"
            >
              <RiCloseLine size={18} />
            </button>
          </div>

          <div className="flex aspect-video w-full items-center justify-center border-b border-stroke bg-surface-1">
            {selectedAlert ? (
              <SnapshotImage
                snapshotUrl={selectedAlert.snapshot_url}
                alt={`${formatAlertCode(selectedAlert.log_id)} snapshot`}
                className="h-full w-full object-contain"
                fallbackClassName="h-32 w-48 border border-stroke-strong bg-surface-1 text-fg-muted"
              />
            ) : (
              <div className="text-caption text-fg-muted">Loading preview…</div>
            )}
          </div>

          <div className="p-6">
            {selectedAlert ? (
              <>
                <div className="mb-5 flex items-center gap-3">
                  <span className="text-xl font-semibold text-fg">
                    {formatAlertCode(selectedAlert.log_id)}
                  </span>
                  <span
                    className={cn(
                      "rounded-sm px-2 py-0.5 text-caption font-bold uppercase tracking-[0.08em]",
                      getAlertBadgeClass(selectedAlert.detection_status),
                    )}
                  >
                    {selectedAlert.detection_status}
                  </span>
                </div>

                <div className="mb-6 space-y-3.5">
                  <div className="flex items-center justify-between text-caption">
                    <span className="font-medium tracking-[0.08em] text-fg-muted">TIMESTAMP</span>
                    <span className="font-medium text-fg-body">
                      {formatFullDateTime(selectedAlert.detected_at)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-caption">
                    <span className="font-medium tracking-[0.08em] text-fg-muted">CAMERA NAME</span>
                    <span className="font-medium text-fg-body">
                      {selectedAlert.camera_name ?? "Unknown Camera"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-caption">
                    <span className="font-medium tracking-[0.08em] text-fg-muted">
                      AI-CONFIDENCE SCORE
                    </span>
                    <span className="rounded bg-danger-subtle px-1.5 py-0.5 font-bold text-danger">
                      {formatAlertConfidence(selectedAlert.confidence_score)}
                    </span>
                  </div>
                </div>

                <div className="mb-6 border-t border-border pt-5">
                  <div className="mb-4 flex items-start justify-between">
                    <div>
                      <div className="mb-1.5 text-caption font-bold uppercase tracking-[0.08em] text-fg-muted">
                        VERIFIED BY
                      </div>
                      <div className="text-caption font-medium text-fg-body">
                        {selectedAlert.verified_by_name ?? "-"}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="mb-1.5 text-caption font-bold uppercase tracking-[0.08em] text-fg-muted">
                        TIME VERIFIED
                      </div>
                      <div className="text-caption text-fg-body">
                        {formatFullDateTime(selectedAlert.verified_at)}
                      </div>
                    </div>
                  </div>

                  {selectedAlert.detection_status === "Dismissed" ||
                  selectedAlert.detection_status === "Resolved" ? (
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="mb-1.5 text-caption font-bold uppercase tracking-[0.08em] text-fg-muted">
                          CLOSED BY
                        </div>
                        <div className="text-caption font-medium text-fg-body">
                          {selectedAlert.closed_by_name ?? "-"}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="mb-1.5 text-caption font-bold uppercase tracking-[0.08em] text-fg-muted">
                          {closedTimeLabel}
                        </div>
                        <div className="text-caption text-fg-body">
                          {formatFullDateTime(selectedAlert.closed_at)}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>

                {alertDetailsQuery.isError ? (
                  <div className="mb-4 rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-caption text-danger">
                    {getApiErrorMessage(
                      alertDetailsQuery.error,
                      "Unable to refresh alert details.",
                    )}
                  </div>
                ) : null}

                {transitionError ? (
                  <div className="mb-4 rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-caption text-danger">
                    {transitionError}
                  </div>
                ) : null}

                {selectedAlert.detection_status === "Unverified" ? (
                  <div className="flex items-center gap-3">
                    <Button
                      variant="outline"
                      className="flex-1 uppercase tracking-[0.08em]"
                      disabled={isTransitionPending}
                      isLoading={dismissMutation.isPending}
                      loadingLabel="Dismissing…"
                      onClick={() => dismissMutation.mutate(selectedAlert.log_id)}
                    >
                      Dismiss Alert
                    </Button>
                    <Button
                      variant="primary"
                      className="flex-1 uppercase tracking-[0.08em]"
                      disabled={isTransitionPending}
                      isLoading={confirmMutation.isPending}
                      loadingLabel="Confirming…"
                      onClick={() => confirmMutation.mutate(selectedAlert.log_id)}
                    >
                      Confirm Alert
                    </Button>
                  </div>
                ) : null}

                {selectedAlert.detection_status === "Ongoing" ? (
                  <div className="flex items-center gap-3">
                    <Button
                      variant="outline"
                      className="flex-1 uppercase tracking-[0.08em]"
                      disabled={isTransitionPending}
                      isLoading={dismissMutation.isPending}
                      loadingLabel="Dismissing…"
                      onClick={() => dismissMutation.mutate(selectedAlert.log_id)}
                    >
                      Dismiss Accident
                    </Button>
                    <Button
                      variant="primary"
                      className="flex-1 uppercase tracking-[0.08em]"
                      disabled={isTransitionPending}
                      isLoading={resolveMutation.isPending}
                      loadingLabel="Resolving…"
                      onClick={() => resolveMutation.mutate(selectedAlert.log_id)}
                    >
                      Resolve Accident
                    </Button>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="py-12 text-center text-secondary text-fg-muted">
                Loading alert details…
              </div>
            )}
          </div>
        </div>
      </Modal>
    </div>
  )
}
