import { useState, type FormEvent } from "react"
import { RiLockPasswordLine } from "@remixicon/react"

import { useMutation } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { ConfirmDiscardModal } from "@/components/ui/ConfirmDiscardModal"
import { resetUserPassword } from "@/api/users"
import type { UserRecord } from "@/api/users"
import { getApiErrorMessage } from "@/api/client"
import { getFieldValidationMessage } from "@/utils/apiFieldErrors"
import { useConfirmedClose } from "@/hooks/useConfirmedClose"
import { validateNewPassword, validatePasswordConfirmation } from "@/utils/passwordValidation"
import { formatShortDateTime } from "@/utils/datetime"
import { getUserFullName } from "@/utils/format"

type ChangePasswordFormState = {
  new_password: string
  confirm_password: string
}

type ChangePasswordFieldErrors = Partial<Record<keyof ChangePasswordFormState, string>>

const EMPTY_FORM: ChangePasswordFormState = {
  new_password: "",
  confirm_password: "",
}

interface ChangePasswordModalProps {
  user: UserRecord
  onClose: () => void
  onSuccess: () => void
}

export function ChangePasswordModal({ user, onClose, onSuccess }: ChangePasswordModalProps) {
  const [form, setForm] = useState<ChangePasswordFormState>(EMPTY_FORM)
  const [fieldErrors, setFieldErrors] = useState<ChangePasswordFieldErrors>({})

  const mutation = useMutation({
    mutationFn: ({ userId, newPassword }: { userId: number; newPassword: string }) =>
      resetUserPassword(userId, { new_password: newPassword }),
    onSuccess,
  })

  const isDirty = form.new_password !== "" || form.confirm_password !== ""
  const { requestClose, isConfirmOpen, confirmDiscard, cancelDiscard } = useConfirmedClose(
    isDirty,
    onClose,
  )

  function updateField<K extends keyof ChangePasswordFormState>(
    field: K,
    value: ChangePasswordFormState[K],
  ) {
    setFieldErrors((current) => ({ ...current, [field]: undefined }))
    mutation.reset()
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const errors: ChangePasswordFieldErrors = {
      new_password: validateNewPassword(form.new_password),
      confirm_password: validatePasswordConfirmation(form.new_password, form.confirm_password),
    }
    setFieldErrors(errors)
    if (Object.values(errors).some(Boolean)) return

    mutation.mutate({
      userId: user.user_id,
      newPassword: form.new_password,
    })
  }

  // The server-side strength check should never fire once the client-side
  // one above agrees with it, but it's the final word — attribute a 422 that
  // still names new_password to that field rather than a generic banner.
  const apiNewPasswordError = mutation.isError
    ? getFieldValidationMessage(mutation.error, "new_password")
    : undefined
  const newPasswordError = fieldErrors.new_password ?? apiNewPasswordError

  const genericError =
    mutation.isError && !apiNewPasswordError
      ? getApiErrorMessage(mutation.error, "Unable to reset password.")
      : null

  return (
    <>
      <Modal
        isOpen
        onClose={requestClose}
        title="Change User Password"
        subtitle="Update a user's password"
        icon={
          <div className="flex h-[64px] w-[64px] shrink-0 items-center justify-center rounded-full border border-stroke">
            <RiLockPasswordLine size={28} className="text-fg" />
          </div>
        }
        className="bg-surface-1 sm:max-w-[540px]"
      >
        <form onSubmit={handleSubmit} className="flex flex-col">
          <hr className="border-t border-stroke mb-6 -mx-6" />

          <div className="flex flex-col gap-4">
            <p className="text-sm font-normal text-fg">
              Changing {getUserFullName(user)}'s account's password...
            </p>

            <div className="flex flex-col gap-4">
              <PasswordInput
                label="New Password"
                value={form.new_password}
                disabled={mutation.isPending}
                error={newPasswordError}
                onChange={(value) => updateField("new_password", value)}
                inputClassName="text-sm text-fg"
                labelClassName="text-sm font-medium text-fg"
              />
              <PasswordInput
                label="Confirm New Password"
                value={form.confirm_password}
                disabled={mutation.isPending}
                error={fieldErrors.confirm_password}
                onChange={(value) => updateField("confirm_password", value)}
                inputClassName="text-sm text-fg"
                labelClassName="text-sm font-medium text-fg"
              />
            </div>

            <div className="text-[12px] font-normal text-fg-muted">
              Must be at least 8 characters long and contain at least 1 number.
            </div>

            <div className="mt-2">
              <p className="rounded-md border border-warning-border bg-warning-subtle px-4 py-3 text-sm font-medium text-warning">
                Resetting this password will sign {getUserFullName(user)} out of every active
                session immediately.
              </p>
            </div>
          </div>

          {genericError ? <p className="mt-4 text-sm text-danger">{genericError}</p> : null}

          <hr className="border-t border-stroke my-6 -mx-6" />

          <div className="flex items-center justify-between gap-4">
            <div className="text-[12px] font-normal text-fg-muted leading-relaxed shrink-0">
              Last Changes: {formatShortDateTime(user.password_changed_at ?? null)}
            </div>
            <div className="flex items-center justify-end gap-2 shrink-0">
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
