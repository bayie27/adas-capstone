import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Modal } from "@/components/ui/Modal"
import { updateUser } from "@/api/users"
import type { ApiUserRole } from "@/api/auth"
import type { UpdateUserInput, UserRecord } from "@/api/users"
import { getApiErrorMessage } from "@/utils/api"
import { formatShortDateTime } from "@/utils/datetime"
import { RiPencilLine } from "@remixicon/react"

type EditUserFormState = {
  first_name: string
  last_name: string
  username: string
  role: ApiUserRole
}

interface EditUserModalProps {
  user: UserRecord
  onClose: () => void
  onSuccess: (user: UserRecord) => void
}

export function EditUserModal({ user, onClose, onSuccess }: EditUserModalProps) {
  const [form, setForm] = useState<EditUserFormState>({
    first_name: user.first_name,
    last_name: user.last_name,
    username: user.username,
    role: user.role,
  })
  const [validationError, setValidationError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: ({ userId, input }: { userId: number; input: UpdateUserInput }) =>
      updateUser(userId, input),
    onSuccess: (updatedUser) => onSuccess(updatedUser),
  })

  function updateField<K extends keyof EditUserFormState>(field: K, value: EditUserFormState[K]) {
    setValidationError(null)
    mutation.reset()
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setValidationError(null)

    const payload: EditUserFormState = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      username: form.username.trim(),
      role: form.role,
    }

    if (!payload.first_name || !payload.last_name || !payload.username) {
      setValidationError("All user fields are required.")
      return
    }

    if (
      payload.first_name === user.first_name &&
      payload.last_name === user.last_name &&
      payload.username === user.username &&
      payload.role === user.role
    ) {
      setValidationError("No user changes to save.")
      return
    }

    mutation.mutate({
      userId: user.user_id,
      input: payload,
    })
  }

  const errorMessage =
    validationError ??
    (mutation.isError ? getApiErrorMessage(mutation.error, "Unable to update user.") : null)

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Edit User"
      subtitle="Update the user's account details and access role"
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-stroke-strong bg-transparent">
          <RiPencilLine size={20} className="text-fg" />
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-6">
        <div className="grid grid-cols-[100px_1fr] gap-4">
          <div className="pt-1 text-xs font-semibold text-fg-body">User</div>
          <div className="space-y-4">
            <div className="mb-2">
              <label className="mb-2 block text-[11px] font-semibold text-fg-body">Role</label>
              <div className="flex items-center gap-8">
                <label className="flex cursor-pointer items-center gap-2 text-xs text-fg-body">
                  <input
                    type="radio"
                    name="editRole"
                    className="accent-white"
                    checked={form.role === "Admin"}
                    onChange={() => updateField("role", "Admin")}
                  />
                  Administrator
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-xs text-fg-body">
                  <input
                    type="radio"
                    name="editRole"
                    className="accent-white"
                    checked={form.role === "Operator"}
                    onChange={() => updateField("role", "Operator")}
                  />
                  Operator
                </label>
              </div>
            </div>

            <div>
              <label className="mb-2 block text-[11px] font-semibold text-fg-body">
                First Name
              </label>
              <input
                type="text"
                value={form.first_name}
                onChange={(event) => updateField("first_name", event.target.value)}
                className="w-full rounded-md border border-stroke bg-surface-1 px-3 py-2 text-sm text-fg focus:border-stroke-strong focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold text-fg-body">Last Name</label>
              <input
                type="text"
                value={form.last_name}
                onChange={(event) => updateField("last_name", event.target.value)}
                className="w-full rounded-md border border-stroke bg-surface-1 px-3 py-2 text-sm text-fg focus:border-stroke-strong focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold text-fg-body">Username</label>
              <input
                type="text"
                value={form.username}
                onChange={(event) => updateField("username", event.target.value)}
                className="w-full rounded-md border border-stroke bg-surface-1 px-3 py-2 text-sm text-fg focus:border-stroke-strong focus:outline-none"
              />
            </div>
          </div>
        </div>

        {errorMessage ? <p className="text-xs text-danger">{errorMessage}</p> : null}

        <div className="h-px w-full bg-surface-3" />

        <div className="flex items-center justify-between">
          <div className="space-y-1 text-[10px] text-fg-muted">
            <div>Date Added: {formatShortDateTime(user.created_at ?? null)}</div>
            <div>Last Changes: {formatShortDateTime(user.updated_at ?? null)}</div>
          </div>
          <div className="flex items-center gap-3">
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
        </div>
      </form>
    </Modal>
  )
}
