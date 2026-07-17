import { useState, type FormEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import AddLineIcon from "remixicon-react/AddLineIcon"
import AlertLineIcon from "remixicon-react/AlertLineIcon"
import CameraLineIcon from "remixicon-react/CameraLineIcon"
import DeleteBinLineIcon from "remixicon-react/DeleteBinLineIcon"
import GlobalLineIcon from "remixicon-react/GlobalLineIcon"
import PencilLineIcon from "remixicon-react/PencilLineIcon"
import RobotLineIcon from "remixicon-react/RobotLineIcon"

import { FilterSelect } from "@/components/ui/FilterSelect"
import { Modal } from "@/components/ui/Modal"
import { NoticeBanner, type NoticeState } from "@/components/ui/NoticeBanner"
import { PaginationFooter } from "@/components/ui/PaginationFooter"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { SearchInput } from "@/components/ui/SearchInput"
import { StatCard } from "@/components/ui/StatCard"
import { Switch } from "@/components/ui/Switch"
import { TableStateRow } from "@/components/ui/TableStateRow"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import { createCamera, deleteCamera, getCameras, updateCamera } from "@/services/cameras"
import type {
  CameraAiStatus,
  CameraConnectionStatus,
  CameraRecord,
  CreateCameraInput,
  UpdateCameraInput,
} from "@/types/cameras"
import { getApiErrorMessage } from "@/utils/api"
import {
  buildCameraUpdatePayload,
  CAMERA_AI_STATUS_OPTIONS,
  CAMERA_CONNECTION_STATUS_OPTIONS,
  getCameraAiClass,
  getCameraConnectionClass,
} from "@/utils/cameras"
import { formatShortDateTime } from "@/utils/datetime"
import { cn } from "@/utils"

const CAMERAS_PAGE_SIZE = 8
const CAMERAS_QUERY_KEY = ["cameras"] as const
const TABLE_COLUMN_COUNT = 5
const INPUT_CLASS =
  "w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 text-sm text-white placeholder-[#555] focus:border-[#555] focus:outline-none"
const SECONDARY_BUTTON_CLASS =
  "rounded-md border border-[#333] bg-transparent px-4 py-2 text-sm font-medium text-[#E4E4E7] transition-colors hover:text-white"
const PRIMARY_BUTTON_CLASS =
  "rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"

type CameraFormState = {
  camera_name: string
  channel_id: string
}

const EMPTY_FORM: CameraFormState = {
  camera_name: "",
  channel_id: "",
}

interface CameraFormFieldsProps {
  form: CameraFormState
  cameraNamePlaceholder?: string
  channelPlaceholder?: string
  onChange: (field: keyof CameraFormState, value: string) => void
}

function CameraFormFields({
  form,
  cameraNamePlaceholder,
  channelPlaceholder,
  onChange,
}: CameraFormFieldsProps) {
  return (
    <>
      <div>
        <label className="mb-2 block text-xs font-semibold text-white">Camera Name</label>
        <input
          type="text"
          value={form.camera_name}
          onChange={(event) => onChange("camera_name", event.target.value)}
          placeholder={cameraNamePlaceholder}
          className={INPUT_CLASS}
        />
      </div>
      <div>
        <label className="mb-2 block text-xs font-semibold text-white">Channel No.</label>
        <input
          type="text"
          value={form.channel_id}
          onChange={(event) => onChange("channel_id", event.target.value)}
          placeholder={channelPlaceholder}
          className={INPUT_CLASS}
        />
      </div>
    </>
  )
}

function parseChannelId(value: string) {
  const parsed = Number.parseInt(value.trim(), 10)

  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null
  }

  return parsed
}

export default function Cameras() {
  const queryClient = useQueryClient()
  const [searchTerm, setSearchTerm] = useState("")
  const [connectionFilter, setConnectionFilter] = useState<CameraConnectionStatus | "all">("all")
  const [aiFilter, setAiFilter] = useState<CameraAiStatus | "all">("all")
  const [isEnabledFilter, setIsEnabledFilter] = useState<"all" | "true" | "false">("all")
  const [notice, setNotice] = useState<NoticeState | null>(null)
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [selectedCamera, setSelectedCamera] = useState<CameraRecord | null>(null)
  const [addForm, setAddForm] = useState<CameraFormState>(EMPTY_FORM)
  const [editForm, setEditForm] = useState<CameraFormState>(EMPTY_FORM)
  const [addValidationError, setAddValidationError] = useState<string | null>(null)
  const [editValidationError, setEditValidationError] = useState<string | null>(null)

  const debouncedSearchTerm = useDebouncedValue(searchTerm.trim(), 300)
  // See Users.tsx: mirror the query total into state so usePagination can clamp
  // the page at read time without an effect.
  const [seenTotal, setSeenTotal] = useState(0)
  const { page, totalPages, offset, rangeStart, rangeEnd, next, prev, reset } = usePagination(
    seenTotal,
    CAMERAS_PAGE_SIZE,
  )

  const camerasQuery = useQuery({
    queryKey: [...CAMERAS_QUERY_KEY, debouncedSearchTerm, connectionFilter, aiFilter, isEnabledFilter, offset],
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

  const invalidateCameraQueries = () => queryClient.invalidateQueries({ queryKey: CAMERAS_QUERY_KEY })

  const createCameraMutation = useMutation({
    mutationFn: createCamera,
    onSuccess: (camera) => {
      setNotice({
        tone: "success",
        message: `${camera.camera_name} was added successfully.`,
      })
      reset()
      closeAddModal()
      invalidateCameraQueries()
    },
  })

  const editCameraMutation = useMutation({
    mutationFn: ({ cameraId, input }: { cameraId: number; input: UpdateCameraInput }) =>
      updateCamera(cameraId, input),
    onSuccess: (camera) => {
      setNotice({
        tone: "success",
        message: `${camera.camera_name} was updated successfully.`,
      })
      closeEditModal()
      invalidateCameraQueries()
    },
  })

  const toggleCameraMutation = useMutation({
    mutationFn: ({ cameraId, input }: { cameraId: number; input: UpdateCameraInput }) =>
      updateCamera(cameraId, input),
    onSuccess: (camera) => {
      setNotice({
        tone: "success",
        message: `${camera.camera_name} was ${camera.is_enabled ? "enabled" : "disabled"}.`,
      })
      invalidateCameraQueries()
    },
  })

  const deleteCameraMutation = useMutation({
    mutationFn: deleteCamera,
    onSuccess: () => {
      setNotice({
        tone: "success",
        message: `${selectedCamera?.camera_name ?? "Camera"} was removed from the active camera list.`,
      })

      if ((camerasQuery.data?.cameras.length ?? 0) === 1 && page > 1) {
        prev()
      }

      closeDeleteModal()
      invalidateCameraQueries()
    },
  })

  const cameras = camerasQuery.data?.cameras ?? []
  const totalFiltered = camerasQuery.data?.total_filtered ?? 0
  if (totalFiltered !== seenTotal) {
    setSeenTotal(totalFiltered)
  }
  const rangeEndValue = rangeEnd(cameras.length)

  function updateAddForm(field: keyof CameraFormState, value: string) {
    setAddValidationError(null)
    createCameraMutation.reset()
    setAddForm((current) => ({ ...current, [field]: value }))
  }

  function updateEditForm(field: keyof CameraFormState, value: string) {
    setEditValidationError(null)
    editCameraMutation.reset()
    setEditForm((current) => ({ ...current, [field]: value }))
  }

  function closeAddModal() {
    setAddForm(EMPTY_FORM)
    setAddValidationError(null)
    createCameraMutation.reset()
    setIsAddOpen(false)
  }

  function closeEditModal() {
    setEditForm(EMPTY_FORM)
    setEditValidationError(null)
    editCameraMutation.reset()
    setSelectedCamera(null)
    setIsEditOpen(false)
  }

  function closeDeleteModal() {
    deleteCameraMutation.reset()
    setSelectedCamera(null)
    setIsDeleteOpen(false)
  }

  function openAddModal() {
    setNotice(null)
    closeAddModal()
    setIsAddOpen(true)
  }

  function openEditModal(camera: CameraRecord) {
    setNotice(null)
    setSelectedCamera(camera)
    setEditValidationError(null)
    editCameraMutation.reset()
    setEditForm({
      camera_name: camera.camera_name,
      channel_id: String(camera.channel_id),
    })
    setIsEditOpen(true)
  }

  function openDeleteModal(camera: CameraRecord) {
    setNotice(null)
    setSelectedCamera(camera)
    deleteCameraMutation.reset()
    setIsDeleteOpen(true)
  }

  function handleCreateCamera(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setNotice(null)
    setAddValidationError(null)

    const cameraName = addForm.camera_name.trim()
    const channelId = parseChannelId(addForm.channel_id)

    if (!cameraName) {
      setAddValidationError("Camera name is required.")
      return
    }

    if (channelId === null) {
      setAddValidationError("Channel number must be a positive whole number.")
      return
    }

    const payload: CreateCameraInput = {
      camera_name: cameraName,
      channel_id: channelId,
    }

    createCameraMutation.mutate(payload)
  }

  function handleEditCamera(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!selectedCamera) {
      return
    }

    setNotice(null)
    setEditValidationError(null)

    const cameraName = editForm.camera_name.trim()
    const channelId = parseChannelId(editForm.channel_id)

    if (!cameraName) {
      setEditValidationError("Camera name is required.")
      return
    }

    if (channelId === null) {
      setEditValidationError("Channel number must be a positive whole number.")
      return
    }

    const payload = buildCameraUpdatePayload(selectedCamera, {
      camera_name: cameraName,
      channel_id: channelId,
    })

    if (Object.keys(payload).length === 0) {
      setEditValidationError("No camera changes to save.")
      return
    }

    editCameraMutation.mutate({
      cameraId: selectedCamera.camera_id,
      input: payload,
    })
  }

  const addErrorMessage =
    addValidationError ??
    (createCameraMutation.isError
      ? getApiErrorMessage(createCameraMutation.error, "Unable to create camera.")
      : null)

  const editErrorMessage =
    editValidationError ??
    (editCameraMutation.isError
      ? getApiErrorMessage(editCameraMutation.error, "Unable to update camera.")
      : null)

  const deleteErrorMessage = deleteCameraMutation.isError
    ? getApiErrorMessage(deleteCameraMutation.error, "Unable to delete camera.")
    : null

  const toggleErrorMessage = toggleCameraMutation.isError
    ? getApiErrorMessage(toggleCameraMutation.error, "Unable to update camera status.")
    : null

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-white">Camera Management</h1>
        <p className="text-xs text-[#737373]">
          Add, configure, and monitor the connection and AI detection status of cameras
        </p>
      </div>

      {notice ? <NoticeBanner notice={notice} /> : null}

      {toggleErrorMessage ? (
        <div className="mb-4 rounded-md border border-[#F87171]/30 bg-[#F87171]/10 px-4 py-3 text-xs text-[#FCA5A5]">
          {toggleErrorMessage}
        </div>
      ) : null}

      <div className="mb-8 grid grid-cols-1 gap-5 md:grid-cols-3">
        <StatCard
          icon={CameraLineIcon}
          title="Total Cameras"
          value={camerasQuery.isLoading ? "..." : camerasQuery.data?.total_cameras ?? 0}
          subtext="All active camera records"
        />
        <StatCard
          icon={GlobalLineIcon}
          title="Network Connected Cameras"
          value={camerasQuery.isLoading ? "..." : camerasQuery.data?.network_connected ?? 0}
          subtext="Currently connected to the network"
        />
        <StatCard
          icon={RobotLineIcon}
          title="Active Detection Cameras"
          value={camerasQuery.isLoading ? "..." : camerasQuery.data?.active_detection ?? 0}
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
            placeholder="Search camera..."
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

        <button
          type="button"
          onClick={openAddModal}
          className="flex items-center gap-1.5 rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-black transition-colors hover:bg-gray-100"
        >
          <AddLineIcon size={14} />
          Add Camera
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-[#2A2A2A] bg-[#111111]">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#2A2A2A] bg-[#141414] text-[#737373]">
                <th className="px-6 py-4 text-xs font-medium">Camera Name</th>
                <th className="px-6 py-4 text-xs font-medium">Channel No.</th>
                <th className="px-6 py-4 text-xs font-medium">Connection Status</th>
                <th className="px-6 py-4 text-xs font-medium">AI Detection Status</th>
                <th className="px-6 py-4 text-right text-xs font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2A2A2A]">
              {camerasQuery.isLoading ? (
                <TableStateRow colSpan={TABLE_COLUMN_COUNT}>Loading cameras...</TableStateRow>
              ) : cameras.length === 0 ? (
                <TableStateRow colSpan={TABLE_COLUMN_COUNT}>
                  No cameras found for the current filters.
                </TableStateRow>
              ) : (
                cameras.map((camera) => (
                  <tr key={camera.camera_id} className="text-[#D4D4D4] transition-colors hover:bg-[#1A1A1A]">
                    <td className="px-6 py-4 text-xs font-medium">{camera.camera_name}</td>
                    <td className="px-6 py-4 text-xs text-[#737373]">{camera.channel_id}</td>
                    <td className="px-6 py-4 text-xs">
                      <span className={cn("font-medium", getCameraConnectionClass(camera.connection_status))}>
                        {camera.connection_status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs">
                      <span className={cn("font-medium", getCameraAiClass(camera.ai_status))}>
                        {camera.ai_status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-3">
                        <Switch
                          checked={camera.is_enabled}
                          disabled={
                            toggleCameraMutation.isPending &&
                            toggleCameraMutation.variables?.cameraId === camera.camera_id
                          }
                          onChange={() => {
                            setNotice(null)
                            toggleCameraMutation.reset()
                            toggleCameraMutation.mutate({
                              cameraId: camera.camera_id,
                              input: { is_enabled: !camera.is_enabled },
                            })
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => openEditModal(camera)}
                          className="text-[#737373] transition-colors hover:text-white"
                        >
                          <PencilLineIcon size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => openDeleteModal(camera)}
                          className="text-[#737373] transition-colors hover:text-white"
                        >
                          <DeleteBinLineIcon size={14} />
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
          page={page}
          totalPages={totalPages}
          rangeStart={rangeStart}
          rangeEnd={rangeEndValue}
          totalFiltered={totalFiltered}
          pageSize={CAMERAS_PAGE_SIZE}
          isFetching={camerasQuery.isFetching}
          onPrev={prev}
          onNext={next}
        />
      </div>

      <Modal
        isOpen={isAddOpen}
        onClose={closeAddModal}
        title="Add Camera"
        subtitle="Assign a name and channel number for the camera."
        icon={
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[#333] bg-transparent">
            <CameraLineIcon size={20} className="text-white" />
          </div>
        }
      >
        <form onSubmit={handleCreateCamera} className="mt-2 space-y-4">
          <CameraFormFields
            form={addForm}
            cameraNamePlaceholder="Rizal Street"
            channelPlaceholder="1"
            onChange={updateAddForm}
          />
          {addErrorMessage ? <p className="text-xs text-[#F87171]">{addErrorMessage}</p> : null}
          <div className="mt-8 flex items-center justify-end gap-3">
            <button type="button" onClick={closeAddModal} className={SECONDARY_BUTTON_CLASS}>
              Cancel
            </button>
            <button type="submit" disabled={createCameraMutation.isPending} className={PRIMARY_BUTTON_CLASS}>
              {createCameraMutation.isPending ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isEditOpen}
        onClose={closeEditModal}
        title="Edit Camera"
        subtitle="Update the camera name and channel number."
        icon={
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[#333] bg-transparent">
            <PencilLineIcon size={20} className="text-white" />
          </div>
        }
      >
        <form onSubmit={handleEditCamera} className="mt-2 space-y-4">
          <CameraFormFields form={editForm} onChange={updateEditForm} />

          {editErrorMessage ? <p className="text-xs text-[#F87171]">{editErrorMessage}</p> : null}

          <div className="mt-8 flex items-end justify-between">
            <div className="space-y-1 text-[10px] text-[#71717A]">
              <div>Date Added: {formatShortDateTime(selectedCamera?.created_at)}</div>
              <div>Last Changes: {formatShortDateTime(selectedCamera?.updated_at)}</div>
            </div>
            <div className="flex items-center gap-3">
              <button type="button" onClick={closeEditModal} className={SECONDARY_BUTTON_CLASS}>
                Cancel
              </button>
              <button type="submit" disabled={editCameraMutation.isPending} className={PRIMARY_BUTTON_CLASS}>
                {editCameraMutation.isPending ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </div>
        </form>
      </Modal>

      <Modal isOpen={isDeleteOpen} onClose={closeDeleteModal} hideClose>
        <div className="flex flex-col items-center pt-6 text-center">
          <AlertLineIcon size={36} className="mb-4 text-[#ef4444]" />
          <h3 className="mb-2 text-[15px] font-bold text-white">Are you absolutely sure?</h3>
          <p className="mb-6 px-4 text-[11px] leading-relaxed text-[#A1A1AA]">
            This action will deactivate camera "{selectedCamera?.camera_name}" and remove it from the active camera list.
          </p>
          {deleteErrorMessage ? <p className="mb-4 text-xs text-[#F87171]">{deleteErrorMessage}</p> : null}
          <div className="flex w-full items-center justify-end gap-3">
            <button
              type="button"
              onClick={closeDeleteModal}
              className="rounded-md border border-[#333] bg-transparent px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-[#1A1A1A]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!selectedCamera || deleteCameraMutation.isPending}
              onClick={() => {
                if (!selectedCamera) {
                  return
                }

                setNotice(null)
                deleteCameraMutation.mutate(selectedCamera.camera_id)
              }}
              className="rounded-md bg-white px-4 py-2 text-xs font-semibold text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {deleteCameraMutation.isPending ? "Deleting..." : "Continue"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
