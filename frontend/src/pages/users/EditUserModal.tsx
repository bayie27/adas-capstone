import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Modal } from "@/components/ui/Modal"
import { Switch } from "@/components/ui/Switch"
import { updateUser } from "@/api/users"
import type { ApiUserRole } from "@/api/auth"
import type { UpdateUserInput, UserRecord } from "@/api/users"
import { getApiErrorMessage } from "@/api/client"
import { formatShortDateTime } from "@/utils/datetime"
import { cn } from "@/utils/cn"
import { RiPencilLine } from "@remixicon/react"

type EditUserFormState = {
  first_name: string
  last_name: string
  username: string
  role: ApiUserRole
  is_active: boolean
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
    is_active: user.is_active,
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
      is_active: form.is_active,
    }

    if (!payload.first_name || !payload.last_name || !payload.username) {
      setValidationError("All user fields are required.")
      return
    }

    if (
      payload.first_name === user.first_name &&
      payload.last_name === user.last_name &&
      payload.username === user.username &&
      payload.role === user.role &&
      payload.is_active === user.is_active
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
                <label
                  className={cn(
                    "flex cursor-pointer items-center gap-2 text-xs text-fg-body",
                    mutation.isPending && "cursor-not-allowed opacity-60",
                  )}
                >
                  <input
                    type="radio"
                    name="editRole"
                    className="accent-white"
                    checked={form.role === "Admin"}
                    disabled={mutation.isPending}
                    onChange={() => updateField("role", "Admin")}
                  />
                  Administrator
                </label>
                <label
                  className={cn(
                    "flex cursor-pointer items-center gap-2 text-xs text-fg-body",
                    mutation.isPending && "cursor-not-allowed opacity-60",
                  )}
                >
                  <input
                    type="radio"
                    name="editRole"
                    className="accent-white"
                    checked={form.role === "Operator"}
                    disabled={mutation.isPending}
                    onChange={() => updateField("role", "Operator")}
                  />
                  Operator
                </label>
              </div>
            </div>

            {/*
              PATCH /api/users/{id} accepts is_active as a first-class field,
              guarded the same way role is (the last active admin cannot be
              deactivated) — but nothing in the UI could ever send it, so that
              guard was unreachable. This makes it reachable. Note the switch
              is effectively one-way from here: GET /api/users/ only ever
              lists is_active=true rows, so a deactivated account's row
              disappears from this table on the next refetch and there is no
              screen left to flip it back — reactivation is a real backend
              capability (see `being_enabled` in routes/users.py) with no
              frontend path to it. Recorded as a follow-up, not fixed here.
            */}
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-fg-body">Active</span>
              <Switch
                checked={form.is_active}
                disabled={mutation.isPending}
                label={form.is_active ? "Deactivate account" : "Activate account"}
                onChange={() => updateField("is_active", !form.is_active)}
              />
            </div>

            <Input
              label="First Name"
              value={form.first_name}
              disabled={mutation.isPending}
              onChange={(event) => updateField("first_name", event.target.value)}
            />
            <Input
              label="Last Name"
              value={form.last_name}
              disabled={mutation.isPending}
              onChange={(event) => updateField("last_name", event.target.value)}
            />
            <Input
              label="Username"
              value={form.username}
              disabled={mutation.isPending}
              onChange={(event) => updateField("username", event.target.value)}
            />
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
            <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>
              Cancel
            </Button>
            <Button type="submit" isLoading={mutation.isPending} loadingLabel="Saving…">
              Save Changes
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
