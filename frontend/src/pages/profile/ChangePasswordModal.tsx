import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { RiLockLine } from "@remixicon/react"

import { Modal } from "@/components/ui/Modal"
import { Button } from "@/components/ui/Button"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { changeMyPassword } from "@/api/users"
import type { NoticeState } from "@/components/ui/NoticeBanner"
import { getApiErrorMessage } from "@/api/client"

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
            className={`mt-4 text-xs ${currentNotice.tone === "success" ? "text-success" : "text-danger"}`}
          >
            {currentNotice.message}
          </p>
        ) : null}

        <hr className="my-6 -mx-6 border-t border-stroke" />

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
            disabled={mutation.isPending}
            isLoading={mutation.isPending}
            loadingLabel="Saving..."
          >
            Save Changes
          </Button>
        </div>
      </form>
    </Modal>
  )
}
