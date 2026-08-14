import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { updateCamera } from "@/api/cameras"
import type { CameraRecord } from "@/api/cameras"
import { getApiErrorMessage } from "@/api/client"
import { buildCameraUpdatePayload } from "@/utils/format"
import { formatShortDateTime } from "@/utils/datetime"
import { CameraFormFields } from "@/pages/cameras/CameraFormFields"
import {
  validateCameraForm,
  type CameraFieldErrors,
  type CameraFormState,
} from "@/pages/cameras/cameraForm"
import { RiPencilLine } from "@remixicon/react"

/** `146:7342` — Edit Camera Form, including its Date Added / Last Changes footer. */
export function EditCameraModal({
  camera,
  onClose,
  onSuccess,
}: {
  camera: CameraRecord
  onClose: () => void
  onSuccess: (camera: CameraRecord) => void
}) {
  const [form, setForm] = useState<CameraFormState>({
    camera_name: camera.camera_name,
    channel_id: String(camera.channel_id),
  })
  const [fieldErrors, setFieldErrors] = useState<CameraFieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (input: Parameters<typeof updateCamera>[1]) =>
      updateCamera(camera.camera_id, input),
    onSuccess,
  })

  function updateField(field: keyof CameraFormState, value: string) {
    setFieldErrors((current) => ({ ...current, [field]: undefined }))
    setFormError(null)
    mutation.reset()
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)

    const { errors, values } = validateCameraForm(form)
    setFieldErrors(errors)
    if (!values) return

    // PATCH is partial — send only what moved, so an unchanged name can't
    // collide with itself on the backend's duplicate check.
    const payload = buildCameraUpdatePayload(camera, values)

    if (Object.keys(payload).length === 0) {
      setFormError("No camera changes to save.")
      return
    }

    mutation.mutate(payload)
  }

  const requestError = mutation.isError
    ? getApiErrorMessage(mutation.error, "Unable to update camera.")
    : null

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Edit Camera"
      subtitle="Update existing camera name & channel no."
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-stroke-strong bg-transparent">
          <RiPencilLine size={20} className="text-fg" />
        </div>
      }
    >
      <form onSubmit={handleSubmit}>
        <div className="space-y-4 border-y border-stroke py-6">
          <CameraFormFields
            form={form}
            errors={fieldErrors}
            disabled={mutation.isPending}
            onChange={updateField}
          />
        </div>

        {(formError ?? requestError) ? (
          <p className="mt-4 text-caption text-danger">{formError ?? requestError}</p>
        ) : null}

        <div className="mt-6 flex items-end justify-between gap-4">
          <div className="space-y-0.5 text-caption text-fg-muted">
            <div>Date Added: {formatShortDateTime(camera.created_at)}</div>
            <div>Last Changes: {formatShortDateTime(camera.updated_at)}</div>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>
              Cancel
            </Button>
            <Button type="submit" isLoading={mutation.isPending} loadingLabel="Saving…">
              Save Changes
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
