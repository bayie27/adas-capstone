import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { resetUserPassword } from "@/api/users"
import type { UserRecord } from "@/api/users"
import { getApiErrorMessage } from "@/api/client"
import { formatShortDateTime } from "@/utils/datetime"
import { getUserFullName } from "@/utils/format"

type ChangePasswordFormState = {
  new_password: string
  confirm_password: string
}

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
  const [validationError, setValidationError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: ({ userId, newPassword }: { userId: number; newPassword: string }) =>
      resetUserPassword(userId, { new_password: newPassword }),
    onSuccess,
  })

  function updateField<K extends keyof ChangePasswordFormState>(
    field: K,
    value: ChangePasswordFormState[K],
  ) {
    setValidationError(null)
    mutation.reset()
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setValidationError(null)

    if (!form.new_password || !form.confirm_password) {
      setValidationError("Both password fields are required.")
      return
    }

    if (form.new_password !== form.confirm_password) {
      setValidationError("Password confirmation does not match.")
      return
    }

    mutation.mutate({
      userId: user.user_id,
      newPassword: form.new_password,
    })
  }

  const errorMessage =
    validationError ??
    (mutation.isError ? getApiErrorMessage(mutation.error, "Unable to reset password.") : null)

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Change User Password"
      subtitle="Update a user's password"
      className="bg-surface-1"
    >
      <form onSubmit={handleSubmit} className="flex flex-col">
        <hr className="border-t border-stroke mb-6 -mx-6" />

        <div className="flex flex-col gap-6">
          <p className="text-base font-normal text-fg">
            Changing {getUserFullName(user)}'s account's password...
          </p>

          <div className="flex flex-col gap-4">
            <PasswordInput
              label="New Password"
              value={form.new_password}
              disabled={mutation.isPending}
              onChange={(value) => updateField("new_password", value)}
              inputClassName="text-base text-fg-muted"
              labelClassName="text-base font-medium text-fg"
            />
            <PasswordInput
              label="Confirm New Password"
              value={form.confirm_password}
              disabled={mutation.isPending}
              onChange={(value) => updateField("confirm_password", value)}
              inputClassName="text-base text-fg-muted"
              labelClassName="text-base font-medium text-fg"
            />
          </div>

          <div className="text-base font-normal text-fg-muted">
            Must be at least 8 characters long and contain at least 1 number.
          </div>

          <div className="mt-2">
            <p className="rounded-md border border-warning-border bg-warning-subtle px-4 py-3 text-sm font-medium text-warning">
              Resetting this password will sign {getUserFullName(user)} out of every active session
              immediately.
            </p>
          </div>
        </div>

        {errorMessage ? <p className="mt-4 text-sm text-danger">{errorMessage}</p> : null}

        <hr className="border-t border-stroke my-6 -mx-6" />

        <div className="flex items-center justify-between">
          <div className="text-sm font-medium text-fg-muted">
            Last Changes: {formatShortDateTime(user.password_changed_at ?? null)}
          </div>
          <div className="flex justify-end gap-2">
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
