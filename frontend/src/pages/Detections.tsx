import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { DateRangePicker } from "@/components/ui/DateRangePicker"
import { ExportButton } from "@/components/ui/ExportButton"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { PaginationFooter } from "@/components/ui/PaginationFooter"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { SearchInput } from "@/components/ui/SearchInput"
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
import { IncidentHandledNotice } from "@/components/ui/IncidentHandledNotice"
import { IncidentDetailModal } from "@/pages/detections/IncidentDetailModal"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import {
  confirmAlert,
  dismissAlert,
  exportAlerts,
  getAlertDetails,
  getAlerts,
  getIncidentConflict,
  resolveAlert,
  snoozeAlert,
} from "@/api/alerts"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { useUserOptions } from "@/hooks/useUserOptions"
import { useNow } from "@/hooks/useNow"
import { useExportJobSubmit } from "@/hooks/useExportJobSubmit"
import { isSnoozedNow, useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
import type { AlertLog, AlertSortField, AlertStatus, ExportFormat, SortOrder } from "@/api/alerts"
import {
  describeSnoozeStatus,
  formatAlertCode,
  formatAlertConfidence,
  getAlertLastHandledBy,
  getAlertLastUpdated,
  getUserFullName,
} from "@/utils/format"
import { getApiErrorMessage } from "@/api/client"
import { formatFullDateTime } from "@/utils/datetime"
import { RiCloseLine, RiEyeLine } from "@remixicon/react"

// Starting page size. PAGE_SIZE_OPTIONS in PaginationFooter is
// [10, 25, 50, 100], so the default must be one of them or the selector
// cannot display its own current value (see M14, which is Cameras' version of
// this problem at a page size of 8).
const ALERTS_PAGE_SIZE = 10
const ACTIVE_ALERT_STATUSES: AlertStatus[] = ["Unverified", "Ongoing"]
const LOG_ALERT_STATUSES: AlertStatus[] = ["Dismissed", "Resolved"]

type TabKey = "ongoing" | "logs"

const TAB_ITEMS = [
  { value: "ongoing" as const, label: "Ongoing" },
  { value: "logs" as const, label: "Logs" },
]

interface SortState {
  key: AlertSortField
  order: SortOrder
}

/**
 * `detected_at desc` is the backend's own default and the only sane resting
 * order for an incident queue — newest first.
 */
const DEFAULT_SORT: SortState = { key: "detected_at", order: "desc" }

/**
 * Column label -> allowlisted sort key. Every value here is a member of
 * `ALERT_SORT_FIELDS`; an unlisted key is a 422, so this table is the only
 * place a key is chosen and it is chosen from the exported allowlist.
 *
 * `Camera Name` sorts by `camera_id`, not by name — the backend allowlist has
 * no `camera_name`. Grouping by camera is what the sort delivers, alphabetical
 * order is not.
 *
 * `Last Handled By` has no allowlisted key (neither `verified_by` nor
 * `closed_by` is sortable) and is deliberately not sortable rather than
 * silently sorting by something else.
 */
const SORTABLE: Record<string, AlertSortField> = {
  "Accident No.": "log_id",
  Timestamp: "detected_at",
  "Camera Name": "camera_id",
  Confidence: "confidence_score",
  Status: "detection_status",
  "Last Updated": "updated_at",
}

export default function Detections() {
  const queryClient = useQueryClient()
  const removeAlert = useAlertStore((state) => state.removeAlert)
  const activateSnooze = useAlertStore((state) => state.activateSnooze)
  const handledByOther = useAlertStore((state) => state.handledByOther)
  const snoozedUntilMap = useAlertStore((state) => state.snoozedUntil)
  const snoozedByMap = useAlertStore((state) => state.snoozedBy)
  const [activeTab, setActiveTab] = useState<TabKey>("ongoing")
  const [logSearch, setLogSearch] = useState("")
  const debouncedLogSearch = useDebouncedValue(logSearch.trim(), 300)
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [cameraId, setCameraId] = useState("")
  const [userId, setUserId] = useState("")

  const role = useAuthStore((state) => state.role)
  const username = useAuthStore((state) => state.username)
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

  // One sort per tab, mirroring the two paginations: the live queue and the
  // archive are different questions and should not share an ordering.
  const [activeSort, setActiveSort] = useState<SortState>(DEFAULT_SORT)
  const [logsSort, setLogsSort] = useState<SortState>(DEFAULT_SORT)

  const activeAlertsQuery = useQuery({
    queryKey: [
      "alerts",
      "active",
      activePagination.offset,
      activePagination.pageSize,
      activeSort.key,
      activeSort.order,
    ],
    queryFn: () =>
      getAlerts({
        status: ACTIVE_ALERT_STATUSES,
        sort_by: activeSort.key,
        sort_order: activeSort.order,
        limit: activePagination.pageSize,
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
      logsPagination.pageSize,
      startDate,
      endDate,
      cameraId,
      userId,
      logsSort.key,
      logsSort.order,
    ],
    queryFn: () =>
      getAlerts({
        status: LOG_ALERT_STATUSES,
        search: debouncedLogSearch || undefined,
        sort_by: logsSort.key,
        sort_order: logsSort.order,
        limit: logsPagination.pageSize,
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
    mutationFn: (format: ExportFormat) =>
      exportAlerts(
        {
          status: LOG_ALERT_STATUSES,
          search: debouncedLogSearch || undefined,
          // Same order as the screen. Without this a CSV of a
          // confidence-sorted view arrives in detected_at order and quietly is
          // not the thing the operator was looking at.
          sort_by: logsSort.key,
          sort_order: logsSort.order,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          camera_id: cameraId ? [Number(cameraId)] : undefined,
          user_id: userId ? [Number(userId)] : undefined,
        },
        format,
      ),
  })

  const exportJobMutation = useExportJobSubmit()

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

  // Snooze mutes an incident in place rather than closing it, so unlike the
  // three mutations above it does not call removeAlert (that queue is the
  // GlobalAlerts popup stack, not this table) — it only updates the cached
  // alert and the shared snoozedUntil map that drives isSnoozedNow.
  const snoozeMutation = useMutation({
    mutationFn: snoozeAlert,
    onSuccess: (snoozedAlert) => {
      queryClient.setQueryData(["alert-details", snoozedAlert.log_id], snoozedAlert)
      setSelectedAlertPreview(snoozedAlert)
      if (snoozedAlert.snoozed_until) {
        activateSnooze(snoozedAlert.log_id, snoozedAlert.snoozed_until, username)
      }
      queryClient.invalidateQueries({ queryKey: ["alerts"] })
    },
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
  const currentSort = activeTab === "ongoing" ? activeSort : logsSort
  const setCurrentSort = activeTab === "ongoing" ? setActiveSort : setLogsSort

  /**
   * D-8(a) — two states. Clicking the active column flips the direction;
   * clicking any other column takes over the sort at `desc`, which is the
   * useful default for every key on this table (newest, highest confidence,
   * most recently updated). There is no third click that clears.
   *
   * Re-sorting changes the query key, so TanStack refetches rather than
   * re-ordering the page in place — a client-side re-sort would reorder one
   * page and lie about the rest, which is why Phase 1 of the earlier
   * remediation removed one.
   */
  const handleSort = (key: string) => {
    const sortKey = key as AlertSortField
    currentPagination.reset()
    setCurrentSort((prev) =>
      prev.key === sortKey
        ? { key: sortKey, order: prev.order === "asc" ? "desc" : "asc" }
        : { key: sortKey, order: "desc" },
    )
  }

  const sortFor = (label: string) => {
    const key = SORTABLE[label]
    if (!key) return undefined
    return {
      key,
      active: currentSort.key === key ? currentSort.order : null,
      onSort: handleSort,
    }
  }

  // Render rows in the server's order. The server paginates (limit/offset), so
  // it defines the total order; re-sorting a single page by a different key
  // would make page boundaries and visible order disagree.
  const currentRows = currentQuery.data?.logs ?? []

  // The store's snoozedUntil map is the live truth — SNOOZE_ACTIVATED and
  // RE_ALARM update it directly without invalidating this table's REST
  // query, so a row's own snoozed_until field can be stale between
  // refetches. Only tick the clock while something on the visible page is
  // actually counting down.
  const anyRowSnoozed = currentRows.some((row) => isSnoozedNow(row.log_id, snoozedUntilMap))
  const now = useNow(anyRowSnoozed, 1000)

  function describeSnoozedRow(row: AlertLog): string | null {
    if (!isSnoozedNow(row.log_id, snoozedUntilMap)) return null
    // SNOOZE_ACTIVATED has carried a real display name since P21 Step 3, for
    // every role — no admin-only lookup needed when this tab actually saw
    // the broadcast (or performed the snooze itself). That only covers
    // incidents snoozed during this connection, though: a row rebuilt from
    // REST on reconnect (RealtimeAlertsBridge's recovery sequence) has no
    // broadcast to carry a name, so it still falls back to the same
    // admin-only user-list lookup (Q10's 100-user cap) or the raw id.
    const broadcastName = snoozedByMap[row.log_id]
    const match = usersQuery.data?.users.find((u) => u.user_id === row.snoozed_by_id)
    const who =
      broadcastName ??
      (match ? getUserFullName(match) : row.snoozed_by_id ? `#${row.snoozed_by_id}` : null)
    return describeSnoozeStatus(
      snoozedUntilMap[row.log_id] ?? row.snoozed_until,
      now,
      who,
      row.snoozed_at,
    )
  }

  const currentTotalFiltered = currentQuery.data?.total_filtered ?? 0
  const rangeStart = currentPagination.rangeStart
  const rangeEndValue = currentPagination.rangeEnd(currentRows.length)

  const selectedAlert = alertDetailsQuery.data ?? selectedAlertPreview

  const isTransitionPending =
    confirmMutation.isPending ||
    dismissMutation.isPending ||
    resolveMutation.isPending ||
    snoozeMutation.isPending

  const transitionFailure =
    confirmMutation.error ?? dismissMutation.error ?? resolveMutation.error ?? snoozeMutation.error

  // A lost race is not a failure to report as one — it is news about what a
  // colleague did. It gets the named notice; everything else gets a banner.
  const transitionConflict = useMemo(
    () => (transitionFailure ? getIncidentConflict(transitionFailure) : null),
    [transitionFailure],
  )

  const transitionError = useMemo(() => {
    if (!transitionFailure || transitionConflict) return null
    return getApiErrorMessage(transitionFailure, "Unable to update alert status.")
  }, [transitionFailure, transitionConflict])

  const closeModal = () => {
    setSelectedAlertId(null)
    setSelectedAlertPreview(null)
    confirmMutation.reset()
    dismissMutation.reset()
    resolveMutation.reset()
    snoozeMutation.reset()
  }

  const openAlertModal = (alert: AlertLog) => {
    setSelectedAlertPreview(alert)
    setSelectedAlertId(alert.log_id)
    confirmMutation.reset()
    dismissMutation.reset()
    resolveMutation.reset()
    snoozeMutation.reset()
  }

  const broadcastHandled =
    selectedAlertId !== null ? (handledByOther[selectedAlertId] ?? null) : null

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
          {/*
            `total_filtered` is already on the list response, so the count is
            free and needs no extra request. It is the count for the SAME
            filter set the export sends.
          */}
          <ExportButton
            rowCount={logsQuery.data?.total_filtered}
            isExporting={exportMutation.isPending}
            exportHasError={exportMutation.isError}
            onExport={(format) => exportMutation.mutate(format)}
            isSubmittingJob={exportJobMutation.isPending}
            onExportJob={(format) =>
              exportJobMutation.mutateAsync({
                report_type: "incidents",
                format,
                status: LOG_ALERT_STATUSES,
                search: debouncedLogSearch || undefined,
                sort_by: logsSort.key,
                sort_order: logsSort.order,
                start_date: startDate || undefined,
                end_date: endDate || undefined,
                camera_id: cameraId ? [Number(cameraId)] : undefined,
                user_id: userId ? [Number(userId)] : undefined,
              })
            }
          />
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

      {/*
        A 413 can still arrive despite the pre-flight — the row count is read
        when the page loads and the filter set can grow before the click. The
        backend's own `detail` names the count, the limit and the async jobs
        endpoint, so it is rendered verbatim rather than replaced with a second
        sentence that can drift out of step with it.
      */}
      {activeTab === "logs" && exportMutation.isError ? (
        <QueryErrorBanner error={exportMutation.error} fallback="Unable to export logs." />
      ) : null}

      {activeTab === "logs" && exportJobMutation.isError ? (
        <QueryErrorBanner
          error={exportJobMutation.error}
          fallback="Unable to start the background export job."
        />
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
            pageSize={currentPagination.pageSize}
            isFetching={currentQuery.isFetching}
            onPrev={currentPagination.prev}
            onNext={currentPagination.next}
            onPageChange={currentPagination.goTo}
            onPageSizeChange={currentPagination.setPageSize}
          />
        }
      >
        <Table>
          <TableHead>
            <TableHeaderCell sort={sortFor("Accident No.")}>Accident No.</TableHeaderCell>
            <TableHeaderCell sort={sortFor("Timestamp")}>Timestamp</TableHeaderCell>
            <TableHeaderCell sort={sortFor("Camera Name")}>Camera Name</TableHeaderCell>
            <TableHeaderCell sort={sortFor("Confidence")}>Confidence</TableHeaderCell>
            <TableHeaderCell sort={sortFor("Status")}>Status</TableHeaderCell>
            <TableHeaderCell>Last Handled By</TableHeaderCell>
            <TableHeaderCell sort={sortFor("Last Updated")}>Last Updated</TableHeaderCell>
            <TableHeaderCell className="text-right">Actions</TableHeaderCell>
          </TableHead>
          <TableBody>
            {currentQuery.isLoading ? (
              <TableStateRow colSpan={8}>
                {activeTab === "ongoing" ? "Loading active alerts…" : "Loading logs…"}
              </TableStateRow>
            ) : currentRows.length === 0 ? (
              <TableStateRow colSpan={8}>
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
                  <TableCell className="tabular-nums">
                    {formatAlertConfidence(item.confidence_score)}
                  </TableCell>
                  <TableCell>
                    <AlertStatusText
                      status={item.detection_status}
                      description={describeSnoozedRow(item)}
                    />
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

      <IncidentDetailModal
        alert={selectedAlert}
        isOpen={selectedAlertId !== null}
        onClose={closeModal}
        isTransitionPending={isTransitionPending}
        isDismissing={dismissMutation.isPending}
        isConfirming={confirmMutation.isPending}
        isResolving={resolveMutation.isPending}
        onDismiss={(logId) => dismissMutation.mutate(logId)}
        onConfirm={(logId) => confirmMutation.mutate(logId)}
        onResolve={(logId) => resolveMutation.mutate(logId)}
        snoozeAction={
          selectedAlert ? (
            <Button
              variant="secondary"
              className="flex-1 uppercase tracking-[0.08em]"
              disabled={isTransitionPending}
              isLoading={snoozeMutation.isPending}
              loadingLabel="Snoozing…"
              onClick={() => snoozeMutation.mutate(selectedAlert.log_id)}
            >
              Snooze
            </Button>
          ) : null
        }
        notice={
          <>
            {alertDetailsQuery.isError ? (
              <div className="mb-4 rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-xs text-danger">
                {getApiErrorMessage(alertDetailsQuery.error, "Unable to refresh alert details.")}
              </div>
            ) : null}
            {/*
              Two sources, one presentation. `transitionConflict` is this
              operator losing a race — a 409 answering their own request.
              `broadcastHandled` is a colleague acting on the incident this
              operator merely has open, which arrives over the socket and
              reaches every tab. The first is a warning; the second is news.
            */}
            {transitionConflict ? <IncidentHandledNotice info={transitionConflict} /> : null}
            {!transitionConflict && broadcastHandled ? (
              <IncidentHandledNotice info={broadcastHandled} tone="neutral" />
            ) : null}
            {transitionError ? (
              <div className="mb-4 rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-xs text-danger">
                {transitionError}
              </div>
            ) : null}
          </>
        }
      />
    </div>
  )
}
