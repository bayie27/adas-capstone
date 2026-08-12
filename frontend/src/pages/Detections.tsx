import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Modal } from "@/components/ui/Modal"
import { PaginationFooter } from "@/components/ui/PaginationFooter"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { SearchInput } from "@/components/ui/SearchInput"
import { SnapshotImage } from "@/components/ui/SnapshotImage"
import { TableStateRow } from "@/components/ui/TableStateRow"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import {
  confirmAlert,
  dismissAlert,
  exportAlertsCsv,
  getAlertDetails,
  getAlerts,
  resolveAlert,
} from "@/services/alerts"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { useUserOptions } from "@/hooks/useUserOptions"
import { useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
import type { AlertLog, AlertStatus } from "@/types/alerts"
import {
  formatAlertCode,
  formatAlertConfidence,
  getAlertBadgeClass,
  getAlertBorderClass,
  getAlertLastHandledBy,
  getAlertLastUpdated,
  getAlertStatusTextClass,
} from "@/utils/alerts"
import { getApiErrorMessage } from "@/utils/api"
import { formatFullDateTime } from "@/utils/datetime"
import { cn } from "@/utils/cn"
import {
  RiArrowRightSLine,
  RiCalendarLine,
  RiCameraLine,
  RiCloseLine,
  RiDownloadLine,
  RiEyeLine,
  RiUserLine,
} from "@remixicon/react"

const ALERTS_PAGE_SIZE = 10
const ACTIVE_ALERT_STATUSES: AlertStatus[] = ["Unverified", "Ongoing"]
const LOG_ALERT_STATUSES: AlertStatus[] = ["Dismissed", "Resolved"]

type TabKey = "ongoing" | "logs"

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

  const usersQuery = useUserOptions({ enabled: role === "Administrator" })
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
      exportAlertsCsv({
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

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-white">Detections</h1>
        <p className="text-xs text-[#737373]">
          Monitor ongoing AI detections and review historical logs to verify reported incidents
        </p>
      </div>

      <div className="mb-6 flex w-fit items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] p-1">
        <button
          type="button"
          onClick={() => setActiveTab("ongoing")}
          className={cn(
            "rounded px-5 py-1.5 text-xs font-medium transition-all duration-200",
            activeTab === "ongoing"
              ? "border border-[#333] bg-[#1A1A1A] text-white shadow-sm"
              : "text-[#737373] hover:text-[#D4D4D4]",
          )}
        >
          Ongoing
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("logs")}
          className={cn(
            "rounded px-5 py-1.5 text-xs font-medium transition-all duration-200",
            activeTab === "logs"
              ? "border border-[#333] bg-[#1A1A1A] text-white shadow-sm"
              : "text-[#737373] hover:text-[#D4D4D4]",
          )}
        >
          Logs
        </button>
      </div>

      {activeTab === "logs" ? (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <SearchInput
              value={logSearch}
              onChange={(value) => {
                logsPagination.reset()
                setLogSearch(value)
              }}
              placeholder="Search accident no. or camera..."
            />
            <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1">
              <RiCalendarLine size={13} className="text-[#737373]" />
              <input
                type="date"
                value={startDate}
                onChange={(e) => {
                  logsPagination.reset()
                  setStartDate(e.target.value)
                }}
                className="bg-transparent text-xs text-[#D4D4D4] focus:outline-none [color-scheme:dark]"
              />
            </div>
            <span className="text-xs text-[#555]">to</span>
            <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1">
              <RiCalendarLine size={13} className="text-[#737373]" />
              <input
                type="date"
                value={endDate}
                onChange={(e) => {
                  logsPagination.reset()
                  setEndDate(e.target.value)
                }}
                className="bg-transparent text-xs text-[#D4D4D4] focus:outline-none [color-scheme:dark]"
              />
            </div>
            <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1">
              <RiCameraLine size={13} className="text-[#737373]" />
              <select
                value={cameraId}
                onChange={(e) => {
                  logsPagination.reset()
                  setCameraId(e.target.value)
                }}
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
            <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-1.5 text-xs text-[#D4D4D4]">
              <RiArrowRightSLine size={13} className="text-[#737373]" />
              Dismissed & Resolved
            </div>
            {role === "Administrator" ? (
              <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1">
                <RiUserLine size={13} className="text-[#737373]" />
                <select
                  value={userId}
                  onChange={(e) => {
                    logsPagination.reset()
                    setUserId(e.target.value)
                  }}
                  className="bg-transparent text-xs text-[#D4D4D4] focus:outline-none"
                >
                  <option value="">All operators</option>
                  {usersQuery.data?.users.map((u) => (
                    <option key={u.user_id} value={u.user_id}>
                      {u.first_name && u.last_name ? `${u.first_name} ${u.last_name}` : u.username}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
            {hasFilters ? (
              <button
                type="button"
                onClick={() => {
                  setStartDate("")
                  setEndDate("")
                  setCameraId("")
                  setUserId("")
                  logsPagination.reset()
                }}
                className="flex items-center gap-1 rounded-md border border-[#2A2A2A] bg-[#141414] px-2 py-1.5 text-xs text-[#737373] transition-colors hover:text-white"
              >
                <RiCloseLine size={12} />
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
            <RiDownloadLine size={13} />
            {exportMutation.isPending ? "Exporting..." : "Export"}
          </button>
        </div>
      ) : (
        <div className="mb-6 flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-1.5 text-xs text-[#D4D4D4]">
            <RiArrowRightSLine size={13} className="text-[#737373]" />
            Unverified & Ongoing
          </div>
          <div className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-1.5 text-xs text-[#D4D4D4]">
            <RiCalendarLine size={13} className="text-[#737373]" />
            Live queue
          </div>
        </div>
      )}

      {activeTab === "logs" && exportMutation.isError ? (
        <QueryErrorBanner error={exportMutation.error} fallback="Unable to export logs CSV." />
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

      <div className="overflow-hidden rounded-xl border border-[#2A2A2A] bg-[#111111]">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#2A2A2A] bg-[#141414] text-[#737373]">
                <th className="px-6 py-4 text-xs font-medium">Accident No.</th>
                <th className="px-6 py-4 text-xs font-medium">Timestamp</th>
                <th className="px-6 py-4 text-xs font-medium">Camera Name</th>
                <th className="px-6 py-4 text-xs font-medium">Status</th>
                <th className="px-6 py-4 text-xs font-medium">Last Handled By</th>
                <th className="px-6 py-4 text-xs font-medium">Last Updated</th>
                <th className="px-6 py-4 text-right text-xs font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2A2A2A]">
              {currentQuery.isLoading ? (
                <TableStateRow colSpan={7}>
                  {activeTab === "ongoing" ? "Loading active alerts..." : "Loading logs..."}
                </TableStateRow>
              ) : currentRows.length === 0 ? (
                <TableStateRow colSpan={7}>
                  {activeTab === "ongoing"
                    ? "No active alerts in the queue."
                    : "No historical logs found for the current filters."}
                </TableStateRow>
              ) : (
                currentRows.map((item) => (
                  <tr
                    key={item.log_id}
                    className="text-[#D4D4D4] transition-colors hover:bg-[#1A1A1A]"
                  >
                    <td className="px-6 py-4 text-xs font-medium">
                      {formatAlertCode(item.log_id)}
                    </td>
                    <td className="px-6 py-4 text-xs text-[#737373]">
                      {formatFullDateTime(item.detected_at)}
                    </td>
                    <td className="px-6 py-4 text-xs">{item.camera_name ?? "Unknown Camera"}</td>
                    <td className="px-6 py-4 text-xs">
                      <span
                        className={cn(
                          "font-medium",
                          getAlertStatusTextClass(item.detection_status),
                        )}
                      >
                        {item.detection_status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-[#737373]">
                      {getAlertLastHandledBy(item)}
                    </td>
                    <td className="px-6 py-4 text-xs text-[#737373]">
                      {getAlertLastUpdated(item)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end">
                        <button
                          type="button"
                          onClick={() => openAlertModal(item)}
                          className="flex h-7 w-7 items-center justify-center rounded border border-[#333] bg-[#1A1A1A] transition-colors hover:bg-[#2A2A2A]"
                        >
                          <RiEyeLine size={14} className="text-white" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

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
        />
      </div>

      <Modal
        isOpen={selectedAlertId !== null}
        onClose={closeModal}
        hideClose
        className={cn(
          "max-w-lg overflow-hidden border-t-4 p-0",
          selectedAlert ? getAlertBorderClass(selectedAlert.detection_status) : "border-t-white",
        )}
      >
        <div className="flex flex-col bg-[#18181B]">
          <div className="flex items-center justify-between border-b border-[#27272A] px-6 py-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-white">
              ACCIDENT DETAILS
            </h2>
            <button
              type="button"
              onClick={closeModal}
              className="text-[#737373] transition-colors hover:text-white"
            >
              <RiCloseLine size={18} />
            </button>
          </div>

          <div className="flex aspect-video w-full items-center justify-center border-b border-[#2A2A2A] bg-[#111]">
            {selectedAlert ? (
              <SnapshotImage
                snapshotUrl={selectedAlert.snapshot_url}
                alt={`${formatAlertCode(selectedAlert.log_id)} snapshot`}
                className="h-full w-full object-contain"
                fallbackClassName="h-32 w-48 border border-[#333] bg-[#1A1A1A] text-[#555]"
              />
            ) : (
              <div className="text-xs text-[#555]">Loading preview...</div>
            )}
          </div>

          <div className="p-6">
            {selectedAlert ? (
              <>
                <div className="mb-5 flex items-center gap-3">
                  <span className="text-xl font-semibold text-white">
                    {formatAlertCode(selectedAlert.log_id)}
                  </span>
                  <span
                    className={cn(
                      "rounded-sm px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                      getAlertBadgeClass(selectedAlert.detection_status),
                    )}
                  >
                    {selectedAlert.detection_status}
                  </span>
                </div>

                <div className="mb-6 space-y-3.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium tracking-wider text-[#737373]">TIMESTAMP</span>
                    <span className="font-medium text-[#D4D4D4]">
                      {formatFullDateTime(selectedAlert.detected_at)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium tracking-wider text-[#737373]">CAMERA NAME</span>
                    <span className="font-medium text-[#D4D4D4]">
                      {selectedAlert.camera_name ?? "Unknown Camera"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium tracking-wider text-[#737373]">
                      AI-CONFIDENCE SCORE
                    </span>
                    <span className="rounded bg-[#ef4444]/10 px-1.5 py-0.5 font-bold text-[#ef4444]">
                      {formatAlertConfidence(selectedAlert.confidence_score)}
                    </span>
                  </div>
                </div>

                <div className="mb-6 border-t border-[#27272A] pt-5">
                  <div className="mb-4 flex items-start justify-between">
                    <div>
                      <div className="mb-1.5 text-[10px] font-bold uppercase tracking-widest text-[#555]">
                        VERIFIED BY
                      </div>
                      <div className="text-xs font-medium text-[#D4D4D4]">
                        {selectedAlert.verified_by_name ?? "-"}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="mb-1.5 text-[10px] font-bold uppercase tracking-widest text-[#555]">
                        TIME VERIFIED
                      </div>
                      <div className="text-xs text-[#D4D4D4]">
                        {formatFullDateTime(selectedAlert.verified_at)}
                      </div>
                    </div>
                  </div>

                  {selectedAlert.detection_status === "Dismissed" ||
                  selectedAlert.detection_status === "Resolved" ? (
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="mb-1.5 text-[10px] font-bold uppercase tracking-widest text-[#555]">
                          CLOSED BY
                        </div>
                        <div className="text-xs font-medium text-[#D4D4D4]">
                          {selectedAlert.closed_by_name ?? "-"}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="mb-1.5 text-[10px] font-bold uppercase tracking-widest text-[#555]">
                          {closedTimeLabel}
                        </div>
                        <div className="text-xs text-[#D4D4D4]">
                          {formatFullDateTime(selectedAlert.closed_at)}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>

                {alertDetailsQuery.isError ? (
                  <div className="mb-4 rounded-md border border-[#F87171]/30 bg-[#F87171]/10 px-3 py-2 text-xs text-[#FCA5A5]">
                    {getApiErrorMessage(
                      alertDetailsQuery.error,
                      "Unable to refresh alert details.",
                    )}
                  </div>
                ) : null}

                {transitionError ? (
                  <div className="mb-4 rounded-md border border-[#F87171]/30 bg-[#F87171]/10 px-3 py-2 text-xs text-[#FCA5A5]">
                    {transitionError}
                  </div>
                ) : null}

                {selectedAlert.detection_status === "Unverified" ? (
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      disabled={isTransitionPending}
                      onClick={() => dismissMutation.mutate(selectedAlert.log_id)}
                      className="flex-1 rounded-md border border-[#333] bg-[#1A1A1A] py-2.5 text-xs font-medium uppercase tracking-wider text-white transition-colors hover:bg-[#2A2A2A] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {dismissMutation.isPending ? "Dismissing..." : "Dismiss Alert"}
                    </button>
                    <button
                      type="button"
                      disabled={isTransitionPending}
                      onClick={() => confirmMutation.mutate(selectedAlert.log_id)}
                      className="flex-1 rounded-md bg-white py-2.5 text-xs font-semibold uppercase tracking-wider text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {confirmMutation.isPending ? "Confirming..." : "Confirm Alert"}
                    </button>
                  </div>
                ) : null}

                {selectedAlert.detection_status === "Ongoing" ? (
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      disabled={isTransitionPending}
                      onClick={() => dismissMutation.mutate(selectedAlert.log_id)}
                      className="flex-1 rounded-md border border-[#333] bg-[#1A1A1A] py-2.5 text-xs font-medium uppercase tracking-wider text-white transition-colors hover:bg-[#2A2A2A] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {dismissMutation.isPending ? "Dismissing..." : "Dismiss Accident"}
                    </button>
                    <button
                      type="button"
                      disabled={isTransitionPending}
                      onClick={() => resolveMutation.mutate(selectedAlert.log_id)}
                      className="flex-1 rounded-md bg-white py-2.5 text-xs font-semibold uppercase tracking-wider text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {resolveMutation.isPending ? "Resolving..." : "Resolve Accident"}
                    </button>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="py-12 text-center text-sm text-[#A1A1AA]">
                Loading alert details...
              </div>
            )}
          </div>
        </div>
      </Modal>
    </div>
  )
}
