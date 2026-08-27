import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { ClearFiltersButton } from "@/components/ui/ClearFiltersButton"
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
import { toast } from "@/store/useToastStore"
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
import { RiEyeLine } from "@remixicon/react"

// Starting page size. PAGE_SIZE_OPTIONS in PaginationFooter is
// [10, 25, 50, 100], so the default must be one of them or the selector
// cannot display its own current value (see M14, which is Cameras' version of
// this problem at a page size of 8).
const ALERTS_PAGE_SIZE = 10

// Export always covers the historical closed-incident archive. Ongoing
// accidents are excluded regardless of the current status filter so that a
// live export is never inflated by in-progress incidents.
const EXPORT_STATUSES: AlertStatus[] = ["Dismissed", "Resolved"]

// Status dropdown options. An empty value means "no filter" (all statuses).
const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "Unverified", label: "Unverified" },
  { value: "Ongoing", label: "Ongoing" },
  { value: "Resolved", label: "Resolved" },
  { value: "Dismissed", label: "Dismissed" },
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

  // "" means no status filter (all statuses shown).
  const [statusFilter, setStatusFilter] = useState("")
  const [logSearch, setLogSearch] = useState("")
  const debouncedLogSearch = useDebouncedValue(logSearch.trim(), 300)
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [cameraId, setCameraId] = useState("")
  const [userId, setUserId] = useState("")

  const role = useAuthStore((state) => state.role)
  const username = useAuthStore((state) => state.username)

  // The clear-filters button appears when any non-search filter is active.
  // logSearch is excluded because SearchInput already has its own clear ×.
  const hasFilters = Boolean(statusFilter || startDate || endDate || cameraId || userId)

  const camerasQuery = useCameraOptions()
  const usersQuery = useUserOptions({ enabled: role === "Admin" })

  const [selectedAlertId, setSelectedAlertId] = useState<number | null>(null)
  const [selectedAlertPreview, setSelectedAlertPreview] = useState<AlertLog | null>(null)

  // Mirror total_filtered into state so usePagination stays stable between
  // fetches (same pattern as Cameras.tsx / Users.tsx).
  const [seenTotal, setSeenTotal] = useState(0)
  const pagination = usePagination(seenTotal, ALERTS_PAGE_SIZE)
  const [sort, setSort] = useState<SortState>(DEFAULT_SORT)

  const alertsQuery = useQuery({
    queryKey: [
      "alerts",
      "list",
      statusFilter,
      debouncedLogSearch,
      pagination.offset,
      pagination.pageSize,
      startDate,
      endDate,
      cameraId,
      userId,
      sort.key,
      sort.order,
    ],
    queryFn: () =>
      getAlerts({
        // Pass a single-element array when a specific status is chosen;
        // omit the field entirely for "All statuses" so the backend
        // returns every status without needing to enumerate them here.
        status: statusFilter ? ([statusFilter] as AlertStatus[]) : undefined,
        search: debouncedLogSearch || undefined,
        sort_by: sort.key,
        sort_order: sort.order,
        limit: pagination.pageSize,
        offset: pagination.offset,
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
          // Export always covers the historical archive only — Ongoing
          // incidents are excluded regardless of the current view filter.
          // The same order as the screen is preserved so a CSV of a
          // confidence-sorted view does not silently revert to detected_at.
          status: EXPORT_STATUSES,
          search: debouncedLogSearch || undefined,
          sort_by: sort.key,
          sort_order: sort.order,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          camera_id: cameraId ? [Number(cameraId)] : undefined,
          user_id: userId ? [Number(userId)] : undefined,
        },
        format,
      ),
  })

  const exportJobMutation = useExportJobSubmit()

  const handleMutationSuccess = (updatedAlert: AlertLog, action: string) => {
    queryClient.setQueryData(["alert-details", updatedAlert.log_id], updatedAlert)
    setSelectedAlertPreview(updatedAlert)
    removeAlert(updatedAlert.log_id)
    toast.success(`Incident #${updatedAlert.log_id} ${action}.`)
    queryClient.invalidateQueries({ queryKey: ["alerts"] })
  }

  const confirmMutation = useMutation({
    mutationFn: confirmAlert,
    onSuccess: (alert) => handleMutationSuccess(alert, "confirmed"),
    onError: (err) => {
      if (!getIncidentConflict(err)) {
        toast.error(getApiErrorMessage(err, "Failed to confirm incident."))
      }
    },
  })

  const dismissMutation = useMutation({
    mutationFn: dismissAlert,
    onSuccess: (alert) => handleMutationSuccess(alert, "dismissed"),
    onError: (err) => {
      if (!getIncidentConflict(err)) {
        toast.error(getApiErrorMessage(err, "Failed to dismiss incident."))
      }
    },
  })

  const resolveMutation = useMutation({
    mutationFn: resolveAlert,
    onSuccess: (alert) => handleMutationSuccess(alert, "resolved"),
    onError: (err) => {
      if (!getIncidentConflict(err)) {
        toast.error(getApiErrorMessage(err, "Failed to resolve incident."))
      }
    },
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
      toast.info(`Incident #${snoozedAlert.log_id} snoozed.`)
      queryClient.invalidateQueries({ queryKey: ["alerts"] })
    },
    onError: (err) => {
      if (!getIncidentConflict(err)) {
        toast.error(getApiErrorMessage(err, "Failed to snooze alert."))
      }
    },
  })

  const total = alertsQuery.data?.total_filtered ?? 0
  if (total !== seenTotal) {
    setSeenTotal(total)
  }

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
    pagination.reset()
    setSort((prev) =>
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
      active: sort.key === key ? sort.order : null,
      onSort: handleSort,
    }
  }

  // Render rows in the server's order. The server paginates (limit/offset), so
  // it defines the total order; re-sorting a single page by a different key
  // would make page boundaries and visible order disagree.
  const currentRows = alertsQuery.data?.logs ?? []

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

  const totalFiltered = alertsQuery.data?.total_filtered ?? 0
  const rangeStart = pagination.rangeStart
  const rangeEndValue = pagination.rangeEnd(currentRows.length)

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

      {/* ── Unified Filter Toolbar ────────────────────────────────────────── */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <SearchInput
            value={logSearch}
            onChange={(value) => {
              pagination.reset()
              setLogSearch(value)
            }}
            placeholder="Search accident no. or camera..."
          />
          <DateRangePicker
            start={startDate}
            end={endDate}
            onStartChange={(value) => {
              pagination.reset()
              setStartDate(value)
            }}
            onEndChange={(value) => {
              pagination.reset()
              setEndDate(value)
            }}
            label="Filter incidents by date"
          />
          <FilterSelect
            value={statusFilter}
            options={STATUS_OPTIONS}
            onChange={(value) => {
              pagination.reset()
              setStatusFilter(value)
            }}
          />
          <FilterSelect
            value={cameraId}
            options={cameraOptions}
            onChange={(value) => {
              pagination.reset()
              setCameraId(value)
            }}
          />
          {role === "Admin" ? (
            <FilterSelect
              value={userId}
              options={userOptions}
              onChange={(value) => {
                pagination.reset()
                setUserId(value)
              }}
            />
          ) : null}
          {hasFilters ? (
            <ClearFiltersButton
              onClick={() => {
                setStatusFilter("")
                setStartDate("")
                setEndDate("")
                setCameraId("")
                setUserId("")
                pagination.reset()
              }}
            />
          ) : null}
        </div>

        {/*
          `total_filtered` is already on the list response, so the count is
          free and needs no extra request. It is the count for the SAME
          filter set the export sends — note export always targets
          EXPORT_STATUSES (Dismissed + Resolved), not the current status chip,
          so the count shown here may differ when an Ongoing/Unverified filter
          is active. A follow-up can conditionally suppress the button in
          those cases.
        */}
        <ExportButton
          rowCount={alertsQuery.data?.total_filtered}
          isExporting={exportMutation.isPending}
          exportHasError={exportMutation.isError}
          onExport={(format) => exportMutation.mutate(format)}
          isSubmittingJob={exportJobMutation.isPending}
          onExportJob={(format) =>
            exportJobMutation.mutateAsync({
              report_type: "incidents",
              format,
              status: EXPORT_STATUSES,
              search: debouncedLogSearch || undefined,
              sort_by: sort.key,
              sort_order: sort.order,
              start_date: startDate || undefined,
              end_date: endDate || undefined,
              camera_id: cameraId ? [Number(cameraId)] : undefined,
              user_id: userId ? [Number(userId)] : undefined,
            })
          }
        />
      </div>

      {/*
        A 413 can still arrive despite the pre-flight — the row count is read
        when the page loads and the filter set can grow before the click. The
        backend's own `detail` names the count, the limit and the async jobs
        endpoint, so it is rendered verbatim rather than replaced with a second
        sentence that can drift out of step with it.
      */}
      {exportMutation.isError ? (
        <QueryErrorBanner error={exportMutation.error} fallback="Unable to export logs." />
      ) : null}

      {exportJobMutation.isError ? (
        <QueryErrorBanner
          error={exportJobMutation.error}
          fallback="Unable to start the background export job."
        />
      ) : null}

      {alertsQuery.isError ? (
        <QueryErrorBanner
          error={alertsQuery.error}
          fallback="Unable to load detections."
          onRetry={() => alertsQuery.refetch()}
        />
      ) : null}

      <TableContainer
        footer={
          <PaginationFooter
            page={pagination.page}
            totalPages={pagination.totalPages}
            rangeStart={rangeStart}
            rangeEnd={rangeEndValue}
            totalFiltered={totalFiltered}
            pageSize={pagination.pageSize}
            isFetching={alertsQuery.isFetching}
            onPrev={pagination.prev}
            onNext={pagination.next}
            onPageChange={pagination.goTo}
            onPageSizeChange={pagination.setPageSize}
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
            {alertsQuery.isLoading ? (
              <TableStateRow colSpan={8}>Loading detections…</TableStateRow>
            ) : currentRows.length === 0 ? (
              <TableStateRow colSpan={8}>
                No detections found for the current filters.
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
