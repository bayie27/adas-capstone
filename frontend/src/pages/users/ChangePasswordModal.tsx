import { useState, type FormEvent } from "react"
import { RiLockPasswordLine } from "@remixicon/react"

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
    <Modal isOpen onClose={onClose} className="bg-surface-2 p-1">
      <form onSubmit={handleSubmit} className="flex flex-col">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4 mb-6">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border border-stroke-strong">
              <RiLockPasswordLine size={28} className="text-fg-body" />
            </div>
            <div className="flex flex-col">
              <h3 className="text-[20px] font-semibold text-fg-body leading-[32px]">
                Change User Password
              </h3>
              <p className="text-[14px] font-normal text-fg-muted leading-[28px]">
                Update a user's password
              </p>
            </div>
          </div>
        </div>
        <hr className="border-t border-stroke-strong mb-6 -mx-7" />

        <div className="flex flex-col gap-4">
          <p className="text-[14px] font-normal text-fg-body leading-[28px] mb-2">
            Changing {getUserFullName(user)}'s account's password...
          </p>

          <div className="flex flex-col gap-4">
            <PasswordInput
              label="New Password"
              value={form.new_password}
              disabled={mutation.isPending}
              onChange={(value) => updateField("new_password", value)}
              inputClassName="border-stroke-strong bg-transparent text-fg-muted text-[14px] h-10"
              labelClassName="text-[14px] font-medium text-fg leading-[28px] mb-2"
            />
            <PasswordInput
              label="Confirm New Password"
              value={form.confirm_password}
              disabled={mutation.isPending}
              onChange={(value) => updateField("confirm_password", value)}
              inputClassName="border-stroke-strong bg-transparent text-fg-muted text-[14px] h-10"
              labelClassName="text-[14px] font-medium text-fg leading-[28px] mb-2"
            />
          </div>

          <div className="text-[14px] font-normal text-fg-muted leading-[28px] mt-2">
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

        <hr className="border-t border-stroke-strong my-6 -mx-7" />

        <div className="flex items-center justify-between">
          <div className="text-[12px] font-normal text-fg-muted leading-[28px]">
            Last Changes: {formatShortDateTime(user.password_changed_at ?? null)}
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              className="border-stroke-strong text-[14px] font-medium text-fg px-4 py-2"
              onClick={onClose}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              className="bg-fg-body text-surface-2 hover:opacity-90 text-[14px] font-medium px-4 py-2"
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
