import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Modal } from "@/components/ui/Modal"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { changeMyPassword } from "@/services/users"
import type { NoticeState } from "@/components/ui/NoticeBanner"
import { getApiErrorMessage } from "@/utils/api"
import { RiLockLine } from "@remixicon/react"

type PasswordFormState = {
  old_password: string
  new_password: string
  confirm_password: string
}

const EMPTY_FORM: PasswordFormState = {
  old_password: "",
  new_password: "",
  confirm_password: "",
}

interface ChangePasswordModalProps {
  onClose: () => void
  onSuccess: () => void
}

export function ChangePasswordModal({ onClose, onSuccess }: ChangePasswordModalProps) {
  const [form, setForm] = useState<PasswordFormState>(EMPTY_FORM)
  const [notice, setNotice] = useState<NoticeState | null>(null)

  const mutation = useMutation({
    mutationFn: changeMyPassword,
    onSuccess,
  })

  function updateField<K extends keyof PasswordFormState>(field: K, value: PasswordFormState[K]) {
    setNotice(null)
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setNotice(null)

    if (!form.old_password || !form.new_password || !form.confirm_password) {
      setNotice({ tone: "error", message: "Complete all password fields." })
      return
    }

    if (form.new_password !== form.confirm_password) {
      setNotice({ tone: "error", message: "New password and confirmation do not match." })
      return
    }

    mutation.mutate({
      old_password: form.old_password,
      new_password: form.new_password,
    })
  }

  const currentNotice =
    notice ??
    (mutation.isError
      ? {
          tone: "error" as const,
          message: getApiErrorMessage(mutation.error, "Unable to update your password."),
        }
      : null)

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Change Password"
      subtitle="Update your account password."
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-stroke-strong bg-transparent">
          <RiLockLine size={20} className="text-fg" />
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-6">
        <div className="space-y-4">
          <PasswordInput
            label="Current Password"
            value={form.old_password}
            autoComplete="current-password"
            onChange={(value) => updateField("old_password", value)}
          />

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

          <p className="text-[10px] text-fg-muted">
            Must be at least 8 characters long and contain at least 1 number.
          </p>
        </div>

        {currentNotice ? (
          <p
            className={`text-xs ${currentNotice.tone === "success" ? "text-success" : "text-danger"}`}
          >
            {currentNotice.message}
          </p>
        ) : null}

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-stroke-strong bg-transparent px-4 py-2 text-xs font-medium text-fg-body transition-colors hover:text-fg"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-md bg-primary px-4 py-2 text-xs font-medium text-fg-on-primary transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {mutation.isPending ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>
    </Modal>
  )
}
