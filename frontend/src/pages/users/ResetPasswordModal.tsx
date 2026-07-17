import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Modal } from "@/components/ui/Modal"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { resetUserPassword } from "@/services/users"
import type { UserRecord } from "@/types/users"
import { getApiErrorMessage } from "@/utils/api"
import { formatShortDateTime } from "@/utils/datetime"
import { getUserFullName } from "@/utils/users"
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

  function updateField<K extends keyof ResetPasswordFormState>(field: K, value: ResetPasswordFormState[K]) {
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
    validationError ?? (mutation.isError ? getApiErrorMessage(mutation.error, "Unable to reset password.") : null)

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Change Password"
      subtitle="Update a user's password"
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[#333] bg-transparent">
          <RiLockLine size={20} className="text-white" />
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-6">
        <div className="h-px w-full bg-[#2A2A2A]" />
        <div className="space-y-4">
          <p className="mb-4 text-xs text-[#A1A1AA]">Changing {getUserFullName(user)}'s account password...</p>
          <PasswordInput
            label="New Password"
            value={form.new_password}
            onChange={(value) => updateField("new_password", value)}
          />
          <PasswordInput
            label="Confirm New Password"
            value={form.confirm_password}
            onChange={(value) => updateField("confirm_password", value)}
          />
          <div className="mt-2 mb-2 text-[10px] text-[#737373]">
            Must be at least 8 characters long and contain at least 1 number.
          </div>
        </div>

        {errorMessage ? <p className="text-xs text-[#F87171]">{errorMessage}</p> : null}

        <div className="h-px w-full bg-[#2A2A2A]" />

        <div className="flex items-center justify-between">
          <div className="text-[10px] text-[#71717A]">
            <div>Last Changes: {formatShortDateTime(user.password_changed_at ?? null)}</div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-[#333] bg-transparent px-4 py-2 text-xs font-medium text-[#E4E4E7] transition-colors hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded-md bg-white px-4 py-2 text-xs font-medium text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {mutation.isPending ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      </form>
    </Modal>
  )
}

