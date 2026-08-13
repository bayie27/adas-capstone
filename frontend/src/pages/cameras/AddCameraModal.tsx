import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Modal } from "@/components/ui/Modal"
import { createCamera } from "@/api/cameras"
import type { CameraRecord, CreateCameraInput } from "@/api/cameras"
import { getApiErrorMessage } from "@/api/client"
import { RiCameraLine } from "@remixicon/react"

type CameraFormState = {
  camera_name: string
  channel_id: string
}

const EMPTY_FORM: CameraFormState = {
  camera_name: "",
  channel_id: "",
}

const INPUT_CLASS =
  "w-full rounded-md border border-stroke bg-surface-1 px-3 py-2 text-sm text-fg placeholder-fg-muted focus:border-stroke-strong focus:outline-none"
const SECONDARY_BUTTON_CLASS =
  "rounded-md border border-stroke-strong bg-transparent px-4 py-2 text-sm font-medium text-fg-body transition-colors hover:text-fg"
const PRIMARY_BUTTON_CLASS =
  "rounded-md bg-primary px-4 py-2 text-sm font-medium text-fg-on-primary transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"

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
        <label className="mb-2 block text-xs font-semibold text-fg">Camera Name</label>
        <input
          type="text"
          value={form.camera_name}
          onChange={(event) => onChange("camera_name", event.target.value)}
          placeholder={cameraNamePlaceholder}
          className={INPUT_CLASS}
        />
      </div>
      <div>
        <label className="mb-2 block text-xs font-semibold text-fg">Channel No.</label>
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

interface AddCameraModalProps {
  onClose: () => void
  onSuccess: (camera: CameraRecord) => void
}

export function AddCameraModal({ onClose, onSuccess }: AddCameraModalProps) {
  const [form, setForm] = useState<CameraFormState>(EMPTY_FORM)
  const [validationError, setValidationError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: createCamera,
    onSuccess,
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

    const payload: CreateCameraInput = {
      camera_name: cameraName,
      channel_id: channelId,
    }

    mutation.mutate(payload)
  }

  const errorMessage =
    validationError ??
    (mutation.isError ? getApiErrorMessage(mutation.error, "Unable to create camera.") : null)

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Add Camera"
      subtitle="Assign a name and channel number for the camera."
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-stroke-strong bg-transparent">
          <RiCameraLine size={20} className="text-fg" />
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="mt-2 space-y-4">
        <CameraFormFields
          form={form}
          cameraNamePlaceholder="Rizal Street"
          channelPlaceholder="1"
          onChange={updateField}
        />
        {errorMessage ? <p className="text-xs text-danger">{errorMessage}</p> : null}
        <div className="mt-8 flex items-center justify-end gap-3">
          <button type="button" onClick={onClose} className={SECONDARY_BUTTON_CLASS}>
            Cancel
          </button>
          <button type="submit" disabled={mutation.isPending} className={PRIMARY_BUTTON_CLASS}>
            {mutation.isPending ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>
    </Modal>
  )
}
