import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Modal } from "@/components/ui/Modal"
import { updateCamera } from "@/services/cameras"
import type { CameraRecord, UpdateCameraInput } from "@/types/cameras"
import { getApiErrorMessage } from "@/utils/api"
import { formatShortDateTime } from "@/utils/datetime"
import { RiPencilLine } from "@remixicon/react"

type CameraFormState = {
  camera_name: string
  channel_id: string
}

const INPUT_CLASS =
  "w-full rounded-md border border-stroke bg-surface-1 px-3 py-2 text-sm text-white placeholder-fg-muted focus:border-stroke-strong focus:outline-none"
const SECONDARY_BUTTON_CLASS =
  "rounded-md border border-stroke-strong bg-transparent px-4 py-2 text-sm font-medium text-fg-body transition-colors hover:text-white"
const PRIMARY_BUTTON_CLASS =
  "rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"

function parseChannelId(value: string) {
  const parsed = Number.parseInt(value.trim(), 10)

  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null
  }

  return parsed
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

interface EditCameraModalProps {
  camera: CameraRecord
  onClose: () => void
  onSuccess: (camera: CameraRecord) => void
}

export function EditCameraModal({ camera, onClose, onSuccess }: EditCameraModalProps) {
  const [form, setForm] = useState<CameraFormState>({
    camera_name: camera.camera_name,
    channel_id: String(camera.channel_id),
  })
  const [validationError, setValidationError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: ({ cameraId, input }: { cameraId: number; input: UpdateCameraInput }) =>
      updateCamera(cameraId, input),
    onSuccess: (updatedCamera) => onSuccess(updatedCamera),
  })

  function updateField(field: keyof CameraFormState, value: string) {
    setValidationError(null)
    mutation.reset()
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setValidationError(null)

    const cameraName = form.camera_name.trim()
    const channelId = parseChannelId(form.channel_id)

    if (!cameraName) {
      setValidationError("Camera name is required.")
      return
    }

    if (channelId === null) {
      setValidationError("Channel number must be a positive whole number.")
      return
    }

    if (cameraName === camera.camera_name && channelId === camera.channel_id) {
      setValidationError("No camera changes to save.")
      return
    }

    const payload: UpdateCameraInput = {
      camera_name: cameraName,
      channel_id: channelId,
    }

    mutation.mutate({
      cameraId: camera.camera_id,
      input: payload,
    })
  }

  const errorMessage =
    validationError ??
    (mutation.isError ? getApiErrorMessage(mutation.error, "Unable to update camera.") : null)

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Edit Camera"
      subtitle="Update the camera name and channel number."
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-stroke-strong bg-transparent">
          <RiPencilLine size={20} className="text-white" />
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="mt-2 space-y-4">
        <CameraFormFields form={form} onChange={updateField} />

        {errorMessage ? <p className="text-xs text-danger">{errorMessage}</p> : null}

        <div className="mt-8 flex items-end justify-between">
          <div className="space-y-1 text-[10px] text-fg-muted">
            <div>Date Added: {formatShortDateTime(camera.created_at)}</div>
            <div>Last Changes: {formatShortDateTime(camera.updated_at)}</div>
          </div>
          <div className="flex items-center gap-3">
            <button type="button" onClick={onClose} className={SECONDARY_BUTTON_CLASS}>
              Cancel
            </button>
            <button type="submit" disabled={mutation.isPending} className={PRIMARY_BUTTON_CLASS}>
              {mutation.isPending ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
