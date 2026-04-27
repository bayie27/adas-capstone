import { useDeferredValue, useEffect, useState, type ElementType, type FormEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import AddLineIcon from "remixicon-react/AddLineIcon"
import AlertLineIcon from "remixicon-react/AlertLineIcon"
import ArrowLeftSLineIcon from "remixicon-react/ArrowLeftSLineIcon"
import ArrowRightSLineIcon from "remixicon-react/ArrowRightSLineIcon"
import CameraLineIcon from "remixicon-react/CameraLineIcon"
import DeleteBinLineIcon from "remixicon-react/DeleteBinLineIcon"
import GlobalLineIcon from "remixicon-react/GlobalLineIcon"
import PencilLineIcon from "remixicon-react/PencilLineIcon"
import RobotLineIcon from "remixicon-react/RobotLineIcon"
import SearchLineIcon from "remixicon-react/SearchLineIcon"

import { Modal } from "@/components/ui/Modal"
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
  formatCameraDateTime,
  getCameraAiClass,
  getCameraConnectionClass,
} from "@/utils/cameras"
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

type NoticeState = {
  tone: "success" | "error"
  message: string
}

type CameraFormState = {
  camera_name: string
  channel_id: string
}

type FilterOption<T extends string> = {
  value: T
  label: string
}

const EMPTY_FORM: CameraFormState = {
  camera_name: "",
  channel_id: "",
}

interface MetricCardProps {
  icon: ElementType
  title: string
  value: string | number
  subtext?: string
}

interface FilterSelectProps<T extends string> {
  value: T
  options: FilterOption<T>[]
  onChange: (value: T) => void
}

interface CameraFormFieldsProps {
  form: CameraFormState
  cameraNamePlaceholder?: string
  channelPlaceholder?: string
  onChange: (field: keyof CameraFormState, value: string) => void
}

function MetricCard({ icon: Icon, title, value, subtext }: MetricCardProps) {
  return (
    <div className="flex h-[160px] flex-col justify-between rounded-xl border border-[#2A2A2A] bg-[#111111] p-5">
      <div>
        <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg border border-[#2A2A2A] bg-[#1E1E1E]">
          <Icon size={17} className="text-[#A1A1AA]" />
        </div>
        <div className="mb-1.5 flex items-center justify-between">
          <h4 className="text-xs text-[#737373]">{title}</h4>
        </div>
        <div className="text-[28px] font-semibold leading-none tracking-tight text-white">{value}</div>
      </div>
      {subtext ? <div className="mt-3 text-xs text-[#555]">{subtext}</div> : null}
    </div>
  )
}

function Switch({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean
  disabled?: boolean
  onChange?: () => void
}) {
  return (
    <button
      type="button"
      onClick={onChange}
      disabled={disabled}
      aria-pressed={checked}
      className={cn(
        "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
        checked ? "bg-white" : "bg-[#3f3f46]",
        disabled ? "cursor-not-allowed opacity-60" : "",
      )}
    >
      <span
        className={cn(
          "inline-block h-3.5 w-3.5 transform rounded-full bg-[#18181b] transition-transform",
          checked ? "translate-x-4" : "translate-x-1",
        )}
      />
    </button>
  )
}

function FilterSelect<T extends string>({ value, options, onChange }: FilterSelectProps<T>) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
        className="appearance-none rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-1.5 pr-8 text-xs text-[#D4D4D4] focus:border-[#52525B] focus:outline-none"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ArrowRightSLineIcon
        size={13}
        className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[#737373]"
      />
    </div>
  )
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
  const [page, setPage] = useState(1)
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

  const deferredSearchTerm = useDeferredValue(searchTerm.trim())
  const offset = (page - 1) * CAMERAS_PAGE_SIZE

  const camerasQuery = useQuery({
    queryKey: [...CAMERAS_QUERY_KEY, deferredSearchTerm, connectionFilter, aiFilter, isEnabledFilter, offset],
    queryFn: () =>
      getCameras({
        search: deferredSearchTerm || undefined,
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
      setPage(1)
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
        setPage((current) => current - 1)
      }

      closeDeleteModal()
      invalidateCameraQueries()
    },
  })

  const cameras = camerasQuery.data?.cameras ?? []
  const totalFiltered = camerasQuery.data?.total_filtered ?? 0
  const totalPages = Math.max(1, Math.ceil(totalFiltered / CAMERAS_PAGE_SIZE))
  const rangeStart = totalFiltered === 0 ? 0 : offset + 1
  const rangeEnd = totalFiltered === 0 ? 0 : offset + cameras.length

  useEffect(() => {
    if (page <= totalPages) {
      return
    }

    setPage(totalPages)
  }, [page, totalPages])

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

      {notice ? (
        <div
          className={cn(
            "mb-4 rounded-md border px-4 py-3 text-xs",
            notice.tone === "success"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-[#F87171]/30 bg-[#F87171]/10 text-[#FCA5A5]",
          )}
        >
          {notice.message}
        </div>
      ) : null}

      {toggleErrorMessage ? (
        <div className="mb-4 rounded-md border border-[#F87171]/30 bg-[#F87171]/10 px-4 py-3 text-xs text-[#FCA5A5]">
          {toggleErrorMessage}
        </div>
      ) : null}

      <div className="mb-8 grid grid-cols-1 gap-5 md:grid-cols-3">
        <MetricCard
          icon={CameraLineIcon}
          title="Total Cameras"
          value={camerasQuery.isLoading ? "..." : camerasQuery.data?.total_cameras ?? 0}
          subtext="All active camera records"
        />
        <MetricCard
          icon={GlobalLineIcon}
          title="Network Connected Cameras"
          value={camerasQuery.isLoading ? "..." : camerasQuery.data?.network_connected ?? 0}
          subtext="Currently connected to the network"
        />
        <MetricCard
          icon={RobotLineIcon}
          title="Active Detection Cameras"
          value={camerasQuery.isLoading ? "..." : camerasQuery.data?.active_detection ?? 0}
          subtext="AI detection running"
        />
      </div>

      {camerasQuery.isError ? (
        <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-[#F87171]/30 bg-[#F87171]/10 px-4 py-3">
          <p className="text-xs text-[#FCA5A5]">
            {getApiErrorMessage(camerasQuery.error, "Unable to load camera records.")}
          </p>
          <button
            type="button"
            onClick={() => camerasQuery.refetch()}
            className="rounded-md border border-[#333] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#1A1A1A]"
          >
            Retry
          </button>
        </div>
      ) : null}

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative">
            <SearchLineIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#555]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(event) => {
                setPage(1)
                setSearchTerm(event.target.value)
              }}
              placeholder="Search camera..."
              className="w-60 rounded-md border border-[#2A2A2A] bg-[#141414] py-1.5 pl-8 pr-4 text-xs text-white focus:border-[#52525B] focus:outline-none"
            />
          </div>

          <FilterSelect
            value={connectionFilter}
            options={CAMERA_CONNECTION_STATUS_OPTIONS}
            onChange={(value) => {
              setPage(1)
              setConnectionFilter(value)
            }}
          />

          <FilterSelect
            value={aiFilter}
            options={CAMERA_AI_STATUS_OPTIONS}
            onChange={(value) => {
              setPage(1)
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
              setPage(1)
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
                <tr>
                  <td colSpan={TABLE_COLUMN_COUNT} className="px-6 py-8 text-center text-xs text-[#A1A1AA]">
                    Loading cameras...
                  </td>
                </tr>
              ) : cameras.length === 0 ? (
                <tr>
                  <td colSpan={TABLE_COLUMN_COUNT} className="px-6 py-8 text-center text-xs text-[#A1A1AA]">
                    No cameras found for the current filters.
                  </td>
                </tr>
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

        <div className="flex items-center justify-between border-t border-[#2A2A2A] px-6 py-3 text-xs text-[#737373]">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              Items per page
              <span className="flex items-center gap-1 rounded border border-[#2A2A2A] bg-[#141414] px-2 py-1 text-white">
                {CAMERAS_PAGE_SIZE}
              </span>
            </div>
            <span>
              {rangeStart}-{rangeEnd} of {totalFiltered}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page === 1 || camerasQuery.isFetching}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              className="flex items-center gap-1 transition-colors hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <ArrowLeftSLineIcon size={14} /> Previous
            </button>
            <div className="flex items-center gap-1">
              <span className="flex h-6 min-w-6 items-center justify-center rounded bg-[#1E1E1E] px-2 font-medium text-white">
                {page}
              </span>
              <span className="text-[#555]">of</span>
              <span>{totalPages}</span>
            </div>
            <button
              type="button"
              disabled={page >= totalPages || camerasQuery.isFetching}
              onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              className="flex items-center gap-1 transition-colors hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next <ArrowRightSLineIcon size={14} />
            </button>
          </div>
        </div>
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
              <div>Date Added: {formatCameraDateTime(selectedCamera?.created_at)}</div>
              <div>Last Changes: {formatCameraDateTime(selectedCamera?.updated_at)}</div>
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
