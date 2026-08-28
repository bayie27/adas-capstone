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
import { RiLockLine } from "@remixicon/react"

type ResetPasswordFormState = {
  new_password: string
  confirm_password: string
}

const EMPTY_FORM: ResetPasswordFormState = {
  new_password: "",
  confirm_password: "",
}

interface ResetPasswordModalProps {
  user: UserRecord
  onClose: () => void
  onSuccess: () => void
}

export function ResetPasswordModal({ user, onClose, onSuccess }: ResetPasswordModalProps) {
  const [form, setForm] = useState<ResetPasswordFormState>(EMPTY_FORM)
  const [validationError, setValidationError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: ({ userId, newPassword }: { userId: number; newPassword: string }) =>
      resetUserPassword(userId, { new_password: newPassword }),
    onSuccess,
  })

  function updateField<K extends keyof ResetPasswordFormState>(
    field: K,
    value: ResetPasswordFormState[K],
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
      title="Change Password"
      subtitle="Update a user's password"
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-stroke-strong bg-transparent">
          <RiLockLine size={20} className="text-fg" />
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-6">
        <div className="h-px w-full bg-surface-3" />
        <div className="space-y-4">
          <p className="mb-4 text-xs text-fg-muted">
            Changing {getUserFullName(user)}'s account password...
          </p>
          <PasswordInput
            label="New Password"
            value={form.new_password}
            disabled={mutation.isPending}
            onChange={(value) => updateField("new_password", value)}
          />
          <PasswordInput
            label="Confirm New Password"
            value={form.confirm_password}
            disabled={mutation.isPending}
            onChange={(value) => updateField("confirm_password", value)}
          />
          <div className="mt-2 mb-2 text-[10px] text-fg-muted">
            Must be at least 8 characters long and contain at least 1 number.
          </div>
        </div>

        {/*
          POST /api/users/{id}/reset-password revokes every session the
          target holds unconditionally — there is no reset that keeps them
          signed in. Shown before the click, not discovered after it.
        */}
        <p className="rounded-md border border-warning-border bg-warning-subtle px-3 py-2 text-caption text-warning">
          Resetting this password will sign {getUserFullName(user)} out of every active session
          immediately.
        </p>

        {errorMessage ? <p className="text-xs text-danger">{errorMessage}</p> : null}

        <div className="h-px w-full bg-surface-3" />

        <div className="flex items-center justify-between gap-6">
          <div className="text-[12px] font-normal text-fg-muted leading-relaxed shrink-0">
            <div>Last Changes: {formatShortDateTime(user.password_changed_at ?? null)}</div>
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
