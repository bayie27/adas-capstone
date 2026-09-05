import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { ConfirmDiscardModal } from "@/components/ui/ConfirmDiscardModal"
import { createCamera } from "@/api/cameras"
import type { CameraRecord } from "@/api/cameras"
import { useConfirmedClose } from "@/hooks/useConfirmedClose"
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

  const isDirty =
    form.camera_name !== EMPTY_CAMERA_FORM.camera_name ||
    form.channel_id !== EMPTY_CAMERA_FORM.channel_id
  const { requestClose, isConfirmOpen, confirmDiscard, cancelDiscard } = useConfirmedClose(
    isDirty,
    onClose,
  )

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
    <>
      <Modal
        isOpen
        onClose={requestClose}
        title="Add Camera"
        subtitle="Assign name and select the channel no. of the camera"
        icon={
          <div className="flex h-[64px] w-[64px] shrink-0 items-center justify-center rounded-full border border-stroke">
            <RiCameraLine size={28} className="text-fg" />
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
            cameraNamePlaceholder="Rizal Street"
            channelPlaceholder="1"
            onChange={updateField}
          />

          {formError ? <p className="mt-4 text-xs text-danger">{formError}</p> : null}

          <hr className="border-t border-stroke my-6 -mx-6" />

          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              className="border-stroke-strong"
              onClick={requestClose}
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
        </form>
      </Modal>
      <ConfirmDiscardModal
        isOpen={isConfirmOpen}
        onCancel={cancelDiscard}
        onDiscard={confirmDiscard}
      />
    </>
  )
}
