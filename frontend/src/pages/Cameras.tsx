import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Button, focusRing } from "@/components/ui/Button"
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
import { usePagination } from "@/hooks/usePagination"
import { deleteCamera, getCameras } from "@/api/cameras"
import type { CameraAiStatus, CameraConnectionStatus, CameraRecord } from "@/api/cameras"
import { CAMERA_AI_STATUS_OPTIONS, CAMERA_CONNECTION_STATUS_OPTIONS } from "@/utils/format"
import { cn } from "@/utils/cn"
import { AddCameraModal } from "@/pages/cameras/AddCameraModal"
import { EditCameraModal } from "@/pages/cameras/EditCameraModal"
import {
  RiAddLine,
  RiCameraLine,
  RiDeleteBinLine,
  RiOrganizationChart,
  RiPencilLine,
  RiRobot2Line,
} from "@remixicon/react"

const CAMERAS_PAGE_SIZE = 8
const CAMERAS_QUERY_KEY = ["cameras"] as const
const TABLE_COLUMN_COUNT = 5

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
  const [notice, setNotice] = useState<NoticeState | null>(null)
  const [modal, setModal] = useState<ModalState>({ kind: "closed" })

  const debouncedSearchTerm = useDebouncedValue(searchTerm.trim(), 300)
  // See Users.tsx: mirror the query total into state so usePagination can clamp
  // the page at read time without an effect.
  const [seenTotal, setSeenTotal] = useState(0)
  const { page, totalPages, offset, rangeStart, rangeEnd, next, prev, goTo, reset } = usePagination(
    seenTotal,
    CAMERAS_PAGE_SIZE,
  )

  const camerasQuery = useQuery({
    queryKey: [
      ...CAMERAS_QUERY_KEY,
      debouncedSearchTerm,
      connectionFilter,
      aiFilter,
      isEnabledFilter,
      offset,
    ],
    queryFn: () =>
      getCameras({
        search: debouncedSearchTerm || undefined,
        connection_status: connectionFilter === "all" ? undefined : [connectionFilter],
        ai_status: aiFilter === "all" ? undefined : [aiFilter],
        is_enabled: isEnabledFilter === "all" ? undefined : isEnabledFilter === "true",
        limit: CAMERAS_PAGE_SIZE,
        offset,
      }),
    placeholderData: (previousData) => previousData,
  })

  const invalidateCameraQueries = () =>
    queryClient.invalidateQueries({ queryKey: CAMERAS_QUERY_KEY })

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

  const cameras = camerasQuery.data?.cameras ?? []
  // §5.9 — kpis describe the whole active population, not the filtered page,
  // so they are read straight off the response and never derived from
  // `cameras`. Deriving them is what made all three cards read 0.
  const kpis = camerasQuery.data?.kpis
  const totalFiltered = camerasQuery.data?.total_filtered ?? 0
  if (totalFiltered !== seenTotal) {
    setSeenTotal(totalFiltered)
  }
  const rangeEndValue = rangeEnd(cameras.length)

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
          subtext="All active camera records"
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
            options={CAMERA_CONNECTION_STATUS_OPTIONS}
            onChange={(value) => {
              reset()
              setConnectionFilter(value)
            }}
          />

          <FilterSelect
            value={aiFilter}
            options={CAMERA_AI_STATUS_OPTIONS}
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
            pageSize={CAMERAS_PAGE_SIZE}
            isFetching={camerasQuery.isFetching}
            onPrev={prev}
            onNext={next}
            onPageChange={goTo}
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
              cameras.map((camera) => (
                <TableRow key={camera.camera_id}>
                  <TableCell className="font-medium text-fg">{camera.camera_name}</TableCell>
                  <TableCell className="text-fg-muted">{camera.channel_id}</TableCell>
                  <TableCell>
                    <CameraConnectionText status={camera.connection_status} />
                  </TableCell>
                  <TableCell>
                    <CameraAiText status={camera.ai_status} />
                  </TableCell>
                  <TableCell className="w-[133px]">
                    <div className="flex items-center gap-3">
                      <Switch checked={camera.is_enabled} disabled />
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
                          "rounded-sm text-fg-muted transition-colors duration-150 hover:text-fg",
                          focusRing,
                        )}
                      >
                        <RiDeleteBinLine size={16} />
                      </button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

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
