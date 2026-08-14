import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { createCamera } from "@/api/cameras"
import type { CameraRecord } from "@/api/cameras"
import { CameraFormFields } from "@/pages/cameras/CameraFormFields"
import {
  describeCameraWriteError,
  EMPTY_CAMERA_FORM,
  validateCameraForm,
  type CameraFieldErrors,
  type CameraFormState,
} from "@/pages/cameras/cameraForm"
import { RiCameraLine } from "@remixicon/react"

/** `146:7278` — Add Camera Form. */
export function AddCameraModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void
  onSuccess: (camera: CameraRecord) => void
}) {
  const [form, setForm] = useState<CameraFormState>(EMPTY_CAMERA_FORM)
  const [fieldErrors, setFieldErrors] = useState<CameraFieldErrors>({})

  const mutation = useMutation({
    mutationFn: createCamera,
    onSuccess,
  })

  function updateField(field: keyof CameraFormState, value: string) {
    setFieldErrors((current) => ({ ...current, [field]: undefined }))
    mutation.reset()
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const { errors, values } = validateCameraForm(form)
    setFieldErrors(errors)
    if (!values) return

    mutation.mutate(values)
  }

  const formError =
    mutation.isError && mutation.variables
      ? describeCameraWriteError(mutation.error, mutation.variables, "Unable to create camera.")
      : null

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Add Camera"
      subtitle="Assign name and select the channel no. of the camera"
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-stroke-strong bg-transparent">
          <RiCameraLine size={20} className="text-fg" />
        </div>
      }
    >
      <form onSubmit={handleSubmit}>
        {/* The frame rules the header off from the fields, and the fields off
            from the footer. */}
        <div className="space-y-4 border-y border-stroke py-6">
          <CameraFormFields
            form={form}
            errors={fieldErrors}
            disabled={mutation.isPending}
            cameraNamePlaceholder="Rizal Street"
            channelPlaceholder="1"
            onChange={updateField}
          />
        </div>

        {formError ? <p className="mt-4 text-caption text-danger">{formError}</p> : null}

        <div className="mt-6 flex items-center justify-end gap-3">
          <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button type="submit" isLoading={mutation.isPending} loadingLabel="Saving…">
            Save Changes
          </Button>
        </div>
      </form>
    </Modal>
  )
}
