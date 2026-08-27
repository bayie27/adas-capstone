import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { updateCamera } from "@/api/cameras"
import type { CameraRecord } from "@/api/cameras"
import { buildCameraUpdatePayload } from "@/utils/format"
import { formatShortDateTime } from "@/utils/datetime"
import { CameraFormFields } from "@/pages/cameras/CameraFormFields"
import {
  describeCameraWriteError,
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
    ? describeCameraWriteError(
        mutation.error,
        {
          // Whichever field was sent is the one that can collide; an unsent
          // field is unchanged and still holds the camera's current value.
          camera_name: mutation.variables?.camera_name ?? camera.camera_name,
          channel_id: mutation.variables?.channel_id ?? camera.channel_id,
        },
        "Unable to update camera.",
      )
    : null

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Edit Camera"
      subtitle="Update existing camera name & channel no."
      icon={
        <div className="flex h-[64px] w-[64px] shrink-0 items-center justify-center rounded-full border border-stroke">
          <RiPencilLine size={28} className="text-fg" />
        </div>
      }
      className="bg-surface-1 sm:max-w-[590px]"
    >
      <form onSubmit={handleSubmit} className="flex flex-col">
        <hr className="border-t border-stroke mb-6 -mx-6" />

        <CameraFormFields
          form={form}
          errors={fieldErrors}
          disabled={mutation.isPending}
          onChange={updateField}
        />

        {(formError ?? requestError) ? (
          <p className="mt-4 text-xs text-danger">{formError ?? requestError}</p>
        ) : null}

        <hr className="border-t border-stroke my-6 -mx-6" />

        <div className="flex items-center justify-between gap-6">
          <div className="flex flex-col text-[12px] font-normal text-fg-muted leading-relaxed shrink-0">
            <div>Date Added: {formatShortDateTime(camera.created_at ?? null)}</div>
            <div>Last Changes: {formatShortDateTime(camera.updated_at ?? null)}</div>
          </div>
          <div className="flex items-center justify-end gap-2 shrink-0">
            <Button
              variant="outline"
              className="border-stroke-strong"
              onClick={onClose}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              isLoading={mutation.isPending}
              loadingLabel="Saving…"
            >
              Save Changes
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
