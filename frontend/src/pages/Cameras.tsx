import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"

import { Badge } from "@/components/ui/Badge"
import { Button, focusRing } from "@/components/ui/Button"
import { ClearFiltersButton } from "@/components/ui/ClearFiltersButton"
import { ConfirmDeleteModal } from "@/components/ui/ConfirmDeleteModal"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { NoticeBanner, type NoticeState } from "@/components/ui/NoticeBanner"
import { PaginationFooter } from "@/components/ui/PaginationFooter"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { SearchInput } from "@/components/ui/SearchInput"
import { StatCard } from "@/components/ui/StatCard"
import { CameraAiText, CameraConnectionText } from "@/components/ui/StatusText"
import { Switch } from "@/components/ui/Switch"
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
import { useNow } from "@/hooks/useNow"
import { usePagination } from "@/hooks/usePagination"
import { deleteCamera, getCameras, restoreCamera, updateCamera } from "@/api/cameras"
import type {
  CameraAiStatus,
  CameraConnectionStatus,
  CameraListResponse,
  CameraRecord,
} from "@/api/cameras"
import { getApiError, getApiErrorMessage } from "@/api/client"
import { shouldApplyCameraEvent } from "@/utils/merge"
import { describeCameraDesiredState, isCameraInCooldown } from "@/utils/format"
import { cn } from "@/utils/cn"
import { AddCameraModal } from "@/pages/cameras/AddCameraModal"
import { CameraDetailPanel } from "@/pages/cameras/CameraDetailPanel"
import { EditCameraModal } from "@/pages/cameras/EditCameraModal"
import {
  RiAddLine,
  RiArrowGoBackLine,
  RiCameraLine,
  RiDeleteBinLine,
  RiOrganizationChart,
  RiPencilLine,
  RiRobot2Line,
} from "@remixicon/react"

// M14: was 8, but PaginationFooter's items-per-page selector only offers
// [10, 25, 50, 100] and cannot display a value outside that set. 10 matches
// ALERTS_PAGE_SIZE and USERS_PAGE_SIZE rather than adding an option just for
// this screen's old default.
const CAMERAS_PAGE_SIZE = 10
const CAMERAS_QUERY_KEY = ["cameras"] as const
const TABLE_COLUMN_COUNT = 5

/**
 * Rewrites one camera across every cached `["cameras", ...]` page — the list
 * is keyed by filters, page and search, so the same row can be held by
 * several queries at once and patching only the active one leaves the others
 * to snap back on the next render.
 */
function patchCachedCamera(
  queryClient: QueryClient,
  cameraId: number,
  patch: (cached: CameraRecord) => CameraRecord,
) {
  queryClient.setQueriesData<CameraListResponse>({ queryKey: CAMERAS_QUERY_KEY }, (existing) =>
    existing
      ? {
          ...existing,
          cameras: existing.cameras.map((camera) =>
            camera.camera_id === cameraId ? patch(camera) : camera,
          ),
        }
      : existing,
  )
}

type ModalState =
  | { kind: "closed" }
  | { kind: "add" }
  | { kind: "edit"; camera: CameraRecord }
  | { kind: "delete"; camera: CameraRecord }

export default function Cameras() {
  const queryClient = useQueryClient()
  const [searchTerm, setSearchTerm] = useState("")
  const [connectionFilter, setConnectionFilter] = useState<CameraConnectionStatus | "all">("all")
  const [aiFilter, setAiFilter] = useState<CameraAiStatus | "all">("all")
  const [isEnabledFilter, setIsEnabledFilter] = useState<"all" | "true" | "false">("all")
  // "active" is a sentinel for "omit the param" — GET /api/cameras/ already
  // defaults to active-only when is_active is absent, so this preserves
  // today's behavior exactly rather than sending an explicit "true".
  const [activeFilter, setActiveFilter] = useState<"active" | "false" | "null">("active")
  const [notice, setNotice] = useState<NoticeState | null>(null)
  const [modal, setModal] = useState<ModalState>({ kind: "closed" })
  // An id, not the row itself — so the panel re-derives against the live
  // query below and reflects a toggle or a broadcast landing while it's open,
  // rather than showing a snapshot frozen at the moment of the click.
  const [detailCameraId, setDetailCameraId] = useState<number | null>(null)

  const debouncedSearchTerm = useDebouncedValue(searchTerm.trim(), 300)

  const hasFilters =
    searchTerm.trim() !== "" ||
    connectionFilter !== "all" ||
    aiFilter !== "all" ||
    isEnabledFilter !== "all" ||
    activeFilter !== "active"

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
    goTo,
    setPageSize,
    reset,
  } = usePagination(seenTotal, CAMERAS_PAGE_SIZE)

  const camerasQuery = useQuery({
    queryKey: [
      ...CAMERAS_QUERY_KEY,
      debouncedSearchTerm,
      connectionFilter,
      aiFilter,
      isEnabledFilter,
      activeFilter,
      pageSize,
      offset,
    ],
    queryFn: () =>
      getCameras({
        search: debouncedSearchTerm || undefined,
        connection_status: connectionFilter === "all" ? undefined : [connectionFilter],
        ai_status: aiFilter === "all" ? undefined : [aiFilter],
        is_enabled: isEnabledFilter === "all" ? undefined : isEnabledFilter === "true",
        is_active: activeFilter === "active" ? undefined : activeFilter,
        limit: pageSize,
        offset,
      }),
    placeholderData: (previousData) => previousData,
  })

  const invalidateCameraQueries = () =>
    queryClient.invalidateQueries({ queryKey: CAMERAS_QUERY_KEY })

  /**
   * The per-row enable/disable toggle. `PATCH /api/cameras/{id}` has always
   * accepted `is_enabled` and audits it as CAMERA_ENABLE / CAMERA_DISABLE;
   * the switch was simply rendered `disabled`.
   *
   * It is optimistic because the operator needs the row to answer instantly,
   * and optimism here races the CAMERA_STATUS_UPDATE broadcast that the same
   * PATCH triggers. `config_version` arbitrates: the optimistic patch flips
   * `is_enabled` and nothing else — bumping the version locally would make
   * the broadcast confirming this very change look stale and be dropped by
   * RealtimeAlertsBridge.
   */
  const toggleEnabledMutation = useMutation({
    mutationFn: ({ camera, nextEnabled }: { camera: CameraRecord; nextEnabled: boolean }) =>
      updateCamera(camera.camera_id, { is_enabled: nextEnabled }),
    onMutate: async ({ camera, nextEnabled }) => {
      await queryClient.cancelQueries({ queryKey: CAMERAS_QUERY_KEY })
      const previous = queryClient.getQueriesData<CameraListResponse>({
        queryKey: CAMERAS_QUERY_KEY,
      })

      patchCachedCamera(queryClient, camera.camera_id, (cached) => ({
        ...cached,
        is_enabled: nextEnabled,
      }))

      return { previous }
    },
    onError: (error, { camera, nextEnabled }, context) => {
      for (const [queryKey, data] of context?.previous ?? []) {
        queryClient.setQueryData(queryKey, data)
      }

      setNotice({
        tone: "error",
        message: getApiErrorMessage(
          error,
          `Unable to ${nextEnabled ? "enable" : "disable"} ${camera.camera_name}.`,
        ),
      })
    },
    onSuccess: (updated) => {
      // The response is the authoritative row — new config_version, new
      // desired state. Apply it under the same merge rule as a broadcast, in
      // case a newer CAMERA_STATUS_UPDATE landed while this was in flight.
      patchCachedCamera(queryClient, updated.camera_id, (cached) =>
        shouldApplyCameraEvent(updated.config_version, cached.config_version) ? updated : cached,
      )

      setNotice({
        tone: "success",
        message: `${updated.camera_name} is now ${updated.is_enabled ? "enabled" : "disabled"}.`,
      })
    },
    // The kpis object is server-computed over the whole active population, so
    // `enabled` / `active_detection` cannot be derived locally from one row.
    onSettled: invalidateCameraQueries,
  })

  const pendingToggleCameraId = toggleEnabledMutation.isPending
    ? toggleEnabledMutation.variables.camera.camera_id
    : null

  const deleteCameraMutation = useMutation({
    mutationFn: deleteCamera,
    onSuccess: () => {
      const deletedCamera = modal.kind === "delete" ? modal.camera : null

      setNotice({
        tone: "success",
        message: `${deletedCamera?.camera_name ?? "Camera"} was removed from the active camera list.`,
      })

      if ((camerasQuery.data?.cameras.length ?? 0) === 1 && page > 1) {
        prev()
      }

      setModal({ kind: "closed" })
      invalidateCameraQueries()
    },
  })

  /**
   * P23 — the counterpart to deleteCameraMutation. Not optimistic (unlike
   * the enable/disable toggle): restoring is rare enough that the round
   * trip isn't worth the complexity, and a restore can fail with a 409 the
   * operator needs to read (a live camera already holds the name/channel).
   */
  const restoreCameraMutation = useMutation({
    mutationFn: restoreCamera,
    onSuccess: (updated) => {
      setNotice({
        tone: "success",
        message: `${updated.camera_name} was restored.`,
      })
      invalidateCameraQueries()
    },
    onError: (error) => {
      setNotice({
        tone: "error",
        message:
          getApiError(error)?.code === "CONFLICT_DUPLICATE"
            ? "A camera with that name or channel already exists. Rename the live camera, or rename this one, then try restoring again."
            : getApiErrorMessage(error, "Unable to restore this camera."),
      })
    },
  })

  const cameras = camerasQuery.data?.cameras ?? []

  const connectionOptions = useMemo(() => {
    const c = camerasQuery.data?.breakdowns?.connection
    return [
      { label: "All Connections", value: "all" as const },
      { label: `Connected (${c?.connected ?? 0})`, value: "Connected" as const },
      { label: `Reconnecting (${c?.reconnecting ?? 0})`, value: "Reconnecting" as const },
      { label: `Disconnected (${c?.disconnected ?? 0})`, value: "Disconnected" as const },
      { label: `Unresponsive (${c?.unresponsive ?? 0})`, value: "Unresponsive" as const },
    ]
  }, [camerasQuery.data?.breakdowns?.connection])

  const aiOptions = useMemo(() => {
    const a = camerasQuery.data?.breakdowns?.ai
    return [
      { label: "All AI States", value: "all" as const },
      { label: `Active (${a?.active ?? 0})`, value: "Active" as const },
      { label: `Paused (${a?.paused ?? 0})`, value: "Paused" as const },
      { label: `Inactive (${a?.inactive ?? 0})`, value: "Inactive" as const },
      { label: `Unresponsive (${a?.unresponsive ?? 0})`, value: "Unresponsive" as const },
    ]
  }, [camerasQuery.data?.breakdowns?.ai])
  // §5.9 — kpis describe the whole active population, not the filtered page,
  // so they are read straight off the response and never derived from
  // `cameras`. Deriving them is what made all three cards read 0.
  const kpis = camerasQuery.data?.kpis
  const totalFiltered = camerasQuery.data?.total_filtered ?? 0
  if (totalFiltered !== seenTotal) {
    setSeenTotal(totalFiltered)
  }
  const rangeEndValue = rangeEnd(cameras.length)
  // Only the cooldown reason counts down; the clock stays still otherwise.
  const now = useNow(cameras.some(isCameraInCooldown))
  const detailCamera = cameras.find((camera) => camera.camera_id === detailCameraId) ?? null

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-fg">Camera Management</h1>
        <p className="text-xs text-fg-muted">
          Add, configure, and monitor the connection and AI detection status of cameras
        </p>
      </div>

      {notice ? <NoticeBanner notice={notice} /> : null}

      <div className="mb-8 grid grid-cols-1 gap-5 md:grid-cols-3">
        <StatCard
          elevated
          icon={RiCameraLine}
          title="Total Cameras"
          value={kpis?.total ?? 0}
          isLoading={camerasQuery.isLoading}
          // `kpis.enabled` was fetched and never shown. It is the only place
          // the population's enabled/disabled split appears, and it belongs
          // next to the total it is a share of.
          subtext={kpis ? `${kpis.enabled} of ${kpis.total} enabled` : "All active camera records"}
        />
        <StatCard
          icon={RiOrganizationChart}
          title="Network Connected Cameras"
          value={kpis?.network_connected ?? 0}
          isLoading={camerasQuery.isLoading}
          subtext="Currently connected to the network"
        />
        <StatCard
          icon={RiRobot2Line}
          title="Active Detection Cameras"
          value={kpis?.active_detection ?? 0}
          isLoading={camerasQuery.isLoading}
          subtext="AI detection running"
        />
      </div>

      {camerasQuery.isError ? (
        <QueryErrorBanner
          error={camerasQuery.error}
          fallback="Unable to load camera records."
          onRetry={() => camerasQuery.refetch()}
        />
      ) : null}

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

          <FilterSelect
            value={connectionFilter}
            options={connectionOptions}
            onChange={(value) => {
              reset()
              setConnectionFilter(value)
            }}
          />

          <FilterSelect
            value={aiFilter}
            options={aiOptions}
            onChange={(value) => {
              reset()
              setAiFilter(value)
            }}
          />

          <FilterSelect
            value={isEnabledFilter}
            options={[
              { value: "all", label: "All Status" },
              { value: "true", label: "Enabled Only" },
              { value: "false", label: "Disabled Only" },
            ]}
            onChange={(value) => {
              reset()
              setIsEnabledFilter(value as "all" | "true" | "false")
            }}
          />

          <FilterSelect
            value={activeFilter}
            options={[
              { value: "active", label: "Active only" },
              { value: "false", label: "Deleted only" },
              { value: "null", label: "All" },
            ]}
            onChange={(value) => {
              setNotice(null)
              reset()
              setActiveFilter(value)
            }}
          />
          {hasFilters ? (
            <ClearFiltersButton
              onClick={() => {
                reset()
                setSearchTerm("")
                setConnectionFilter("all")
                setAiFilter("all")
                setIsEnabledFilter("all")
                setActiveFilter("active")
              }}
            />
          ) : null}
        </div>

        <Button
          size="sm"
          onClick={() => {
            setNotice(null)
            setModal({ kind: "add" })
          }}
        >
          <RiAddLine size={14} />
          Add Camera
        </Button>
      </div>

      <TableContainer
        footer={
          <PaginationFooter
            page={page}
            totalPages={totalPages}
            rangeStart={rangeStart}
            rangeEnd={rangeEndValue}
            totalFiltered={totalFiltered}
            pageSize={pageSize}
            isFetching={camerasQuery.isFetching}
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
            <TableHeaderCell>Channel No.</TableHeaderCell>
            <TableHeaderCell>Connection Status</TableHeaderCell>
            <TableHeaderCell>AI Detection Status</TableHeaderCell>
            {/* `37:74` fixes the actions column at 133px and left-aligns it, so
                the toggle sits on a stable x across every row. */}
            <TableHeaderCell className="w-[133px]">Actions</TableHeaderCell>
          </TableHead>
          <TableBody>
            {camerasQuery.isLoading ? (
              <TableStateRow colSpan={TABLE_COLUMN_COUNT}>Loading cameras...</TableStateRow>
            ) : cameras.length === 0 ? (
              <TableStateRow colSpan={TABLE_COLUMN_COUNT}>
                No cameras found for the current filters.
              </TableStateRow>
            ) : (
              cameras.map((camera) => {
                // GET /api/cameras/{id} (what the detail panel fetches)
                // stays active-only, same as before P23 — a soft-deleted
                // row has nothing there to open.
                const isRestoring =
                  restoreCameraMutation.isPending &&
                  restoreCameraMutation.variables === camera.camera_id

                return (
                  <TableRow
                    key={camera.camera_id}
                    className={camera.is_active ? "cursor-pointer" : undefined}
                    onClick={() => {
                      if (camera.is_active) setDetailCameraId(camera.camera_id)
                    }}
                  >
                    <TableCell className="font-medium text-fg">
                      {camera.camera_name}
                      {!camera.is_active ? (
                        <Badge variant="subtle" tone="neutral" uppercase={false} className="ml-2">
                          Deleted
                        </Badge>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-fg-muted">{camera.channel_id}</TableCell>
                    <TableCell>
                      <CameraConnectionText status={camera.connection_status} />
                    </TableCell>
                    <TableCell>
                      <CameraAiText
                        status={camera.ai_status}
                        description={describeCameraDesiredState(camera, now)}
                      />
                    </TableCell>
                    <TableCell className="w-[133px]" onClick={(event) => event.stopPropagation()}>
                      {camera.is_active ? (
                        <div className="flex items-center gap-3">
                          <Switch
                            checked={camera.is_enabled}
                            label={`${camera.is_enabled ? "Disable" : "Enable"} ${camera.camera_name}`}
                            disabled={pendingToggleCameraId === camera.camera_id}
                            onChange={() => {
                              setNotice(null)
                              toggleEnabledMutation.mutate({
                                camera,
                                nextEnabled: !camera.is_enabled,
                              })
                            }}
                          />
                          <button
                            type="button"
                            aria-label={`Edit ${camera.camera_name}`}
                            onClick={() => {
                              setNotice(null)
                              setModal({ kind: "edit", camera })
                            }}
                            className={cn(
                              "rounded-sm text-fg-muted transition-colors duration-150 hover:text-fg",
                              focusRing,
                            )}
                          >
                            <RiPencilLine size={16} />
                          </button>
                          <button
                            type="button"
                            aria-label={`Delete ${camera.camera_name}`}
                            onClick={() => {
                              setNotice(null)
                              setModal({ kind: "delete", camera })
                            }}
                            className={cn(
                              "rounded-sm text-fg-muted transition-colors duration-150 hover:text-danger",
                              focusRing,
                            )}
                          >
                            <RiDeleteBinLine size={16} />
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          aria-label={`Restore ${camera.camera_name}`}
                          disabled={isRestoring}
                          onClick={() => {
                            setNotice(null)
                            restoreCameraMutation.mutate(camera.camera_id)
                          }}
                          className={cn(
                            "flex items-center gap-1.5 rounded-sm text-xs text-fg-muted transition-colors duration-150 hover:text-fg",
                            "disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:text-fg-muted",
                            focusRing,
                          )}
                        >
                          <RiArrowGoBackLine size={16} />
                          {isRestoring ? "Restoring…" : "Restore"}
                        </button>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <CameraDetailPanel
        camera={detailCamera}
        isOpen={detailCameraId !== null}
        onClose={() => setDetailCameraId(null)}
        now={now}
      />

      {modal.kind === "add" && (
        <AddCameraModal
          onClose={() => setModal({ kind: "closed" })}
          onSuccess={(camera) => {
            setNotice({
              tone: "success",
              message: `${camera.camera_name} was added successfully.`,
            })
            reset()
            setModal({ kind: "closed" })
            invalidateCameraQueries()
          }}
        />
      )}

      {modal.kind === "edit" && (
        <EditCameraModal
          camera={modal.camera}
          onClose={() => setModal({ kind: "closed" })}
          onSuccess={(camera) => {
            setNotice({
              tone: "success",
              message: `${camera.camera_name} was updated successfully.`,
            })
            setModal({ kind: "closed" })
            invalidateCameraQueries()
          }}
        />
      )}

      <ConfirmDeleteModal
        isOpen={modal.kind === "delete"}
        title="Are you absolutely sure?"
        description={
          modal.kind === "delete"
            ? `This action will deactivate camera "${modal.camera.camera_name}" and remove it from the active camera list.`
            : ""
        }
        isPending={deleteCameraMutation.isPending}
        error={deleteCameraMutation.error}
        errorMessage={
          getApiError(deleteCameraMutation.error)?.code === "PRECONDITION_FAILED"
            ? "This camera has an open incident. Resolve or dismiss it under Detections first — deleting it now would strand the incident on a camera that no longer exists."
            : null
        }
        onClose={() => setModal({ kind: "closed" })}
        onConfirm={() => {
          if (modal.kind === "delete") {
            setNotice(null)
            deleteCameraMutation.mutate(modal.camera.camera_id)
          }
        }}
      />
    </div>
  )
}
