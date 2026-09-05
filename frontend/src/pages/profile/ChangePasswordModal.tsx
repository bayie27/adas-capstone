import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { RiLockLine } from "@remixicon/react"

import { Modal } from "@/components/ui/Modal"
import { Button } from "@/components/ui/Button"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { NoticeBanner, type NoticeState } from "@/components/ui/NoticeBanner"
import { ConfirmDiscardModal } from "@/components/ui/ConfirmDiscardModal"
import { changeMyPassword } from "@/api/users"
import { getApiError, getApiErrorMessage } from "@/api/client"
import { getFieldValidationMessage } from "@/utils/apiFieldErrors"
import { useConfirmedClose } from "@/hooks/useConfirmedClose"
import {
  validateNewPassword,
  validatePasswordConfirmation,
  validateRequiredPassword,
} from "@/utils/passwordValidation"

type PasswordFormState = {
  old_password: string
  new_password: string
  confirm_password: string
}

type PasswordFieldErrors = Partial<Record<keyof PasswordFormState, string>>

const EMPTY_FORM: PasswordFormState = {
  old_password: "",
  new_password: "",
  confirm_password: "",
}

interface ChangePasswordModalProps {
  onClose: () => void
  onSuccess: () => void
}

/**
 * Turns a failed password change into field-level messages.
 *
 * The self-service route (`PATCH /me/password`) answers a wrong current
 * password with a plain 400, not a validation error — that's the one case
 * worth naming explicitly. Anything else that names `old_password` or
 * `new_password` in a 422 (the client-side check above should have already
 * caught it, but the server is the final word) is attributed to that field
 * too; everything else falls back to one generic message.
 */
function describePasswordChangeError(error: unknown): {
  fieldErrors: PasswordFieldErrors
  generic?: string
} {
  if (getApiError(error)?.status === 400) {
    return {
      fieldErrors: {
        old_password: getApiErrorMessage(error, "Current password is incorrect."),
      },
    }
  }

  const fieldErrors: PasswordFieldErrors = {
    old_password: getFieldValidationMessage(error, "old_password"),
    new_password: getFieldValidationMessage(error, "new_password"),
  }
  if (fieldErrors.old_password || fieldErrors.new_password) {
    return { fieldErrors }
  }

  return {
    fieldErrors: {},
    generic: getApiErrorMessage(error, "Unable to update your password."),
  }
}

export function ChangePasswordModal({ onClose, onSuccess }: ChangePasswordModalProps) {
  const [form, setForm] = useState<PasswordFormState>(EMPTY_FORM)
  const [fieldErrors, setFieldErrors] = useState<PasswordFieldErrors>({})
  const [notice, setNotice] = useState<NoticeState | null>(null)

  const mutation = useMutation({
    mutationFn: changeMyPassword,
    onSuccess,
  })

  const isDirty =
    form.old_password !== "" || form.new_password !== "" || form.confirm_password !== ""
  const { requestClose, isConfirmOpen, confirmDiscard, cancelDiscard } = useConfirmedClose(
    isDirty,
    onClose,
  )

  function updateField<K extends keyof PasswordFormState>(field: K, value: PasswordFormState[K]) {
    setNotice(null)
    setFieldErrors((current) => ({ ...current, [field]: undefined }))
    mutation.reset()
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setNotice(null)

    const errors: PasswordFieldErrors = {
      old_password: validateRequiredPassword(form.old_password, "Current password"),
      new_password: validateNewPassword(form.new_password),
      confirm_password: validatePasswordConfirmation(form.new_password, form.confirm_password),
    }
    setFieldErrors(errors)
    if (Object.values(errors).some(Boolean)) return

    mutation.mutate({
      old_password: form.old_password,
      new_password: form.new_password,
    })
  }

  const apiOutcome = mutation.isError ? describePasswordChangeError(mutation.error) : null
  const oldPasswordError = fieldErrors.old_password ?? apiOutcome?.fieldErrors.old_password
  const newPasswordError = fieldErrors.new_password ?? apiOutcome?.fieldErrors.new_password
  const confirmPasswordError = fieldErrors.confirm_password
  const currentNotice =
    notice ?? (apiOutcome?.generic ? { tone: "error" as const, message: apiOutcome.generic } : null)

  return (
    <>
      <Modal
        isOpen
        onClose={requestClose}
        title="Change Password"
        subtitle="Update your account password."
        icon={
          <div className="flex h-[64px] w-[64px] shrink-0 items-center justify-center rounded-full border border-stroke">
            <RiLockLine size={28} className="text-fg" />
          </div>
        }
      >
        <form onSubmit={handleSubmit} className="flex flex-col">
          <hr className="mb-6 -mx-6 border-t border-stroke" />

          <div className="space-y-4">
            <PasswordInput
              label="Current Password"
              value={form.old_password}
              autoComplete="current-password"
              error={oldPasswordError}
              onChange={(value) => updateField("old_password", value)}
            />

            <PasswordInput
              label="New Password"
              value={form.new_password}
              error={newPasswordError}
              onChange={(value) => updateField("new_password", value)}
            />

            <PasswordInput
              label="Confirm New Password"
              value={form.confirm_password}
              error={confirmPasswordError}
              onChange={(value) => updateField("confirm_password", value)}
            />

            <p className="text-[12px] text-fg-muted">
              Must be at least 8 characters long and contain at least 1 number.
            </p>
          </div>

          {currentNotice ? <NoticeBanner notice={currentNotice} /> : null}

          <hr className="my-6 -mx-6 border-t border-stroke" />

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
              disabled={mutation.isPending}
              isLoading={mutation.isPending}
              loadingLabel="Saving..."
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
