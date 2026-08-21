import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { RiPencilLine } from "@remixicon/react"

import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Modal } from "@/components/ui/Modal"
import { updateUser } from "@/api/users"
import type { ApiUserRole } from "@/api/auth"
import type { UpdateUserInput, UserRecord } from "@/api/users"
import { getApiErrorMessage } from "@/api/client"
import { formatShortDateTime } from "@/utils/datetime"
import { cn } from "@/utils/cn"

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
        <div className="flex h-[64px] w-[64px] shrink-0 items-center justify-center rounded-full border border-stroke">
          <RiPencilLine size={28} className="text-fg" />
        </div>
      }
      className="bg-surface-1 sm:max-w-[700px]"
    >
      <form onSubmit={handleSubmit} className="flex flex-col">
        <hr className="border-t border-stroke mb-6 -mx-6" />

        <div className="grid grid-cols-[150px_1fr] gap-x-8 gap-y-6">
          <div className="text-base font-medium text-fg">User</div>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-[20px] mb-2">
              <div className="text-sm font-medium text-fg">Role</div>
              <div className="flex justify-between items-start">
                <label
                  className={cn(
                    "flex flex-1 cursor-pointer items-center gap-2 text-sm font-normal text-fg",
                    mutation.isPending && "cursor-not-allowed opacity-60",
                  )}
                >
                  <input
                    type="radio"
                    name="editRole"
                    className="accent-white h-4 w-4 border-fg"
                    checked={form.role === "Admin"}
                    disabled={mutation.isPending}
                    onChange={() => updateField("role", "Admin")}
                  />
                  Administrator
                </label>
                <label
                  className={cn(
                    "flex flex-1 cursor-pointer items-center gap-2 text-sm font-normal text-fg",
                    mutation.isPending && "cursor-not-allowed opacity-60",
                  )}
                >
                  <input
                    type="radio"
                    name="editRole"
                    className="accent-white h-4 w-4 border-fg"
                    checked={form.role === "Operator"}
                    disabled={mutation.isPending}
                    onChange={() => updateField("role", "Operator")}
                  />
                  Operator
                </label>
              </div>
            </div>

            <Input
              label="First Name"
              value={form.first_name}
              disabled={mutation.isPending}
              onChange={(event) => updateField("first_name", event.target.value)}
              className="text-sm text-fg"
              labelClassName="text-sm font-medium text-fg"
            />
            <Input
              label="Last Name"
              value={form.last_name}
              disabled={mutation.isPending}
              onChange={(event) => updateField("last_name", event.target.value)}
              className="text-sm text-fg"
              labelClassName="text-sm font-medium text-fg"
            />
            <Input
              label="Username"
              value={form.username}
              disabled={mutation.isPending}
              onChange={(event) => updateField("username", event.target.value)}
              className="text-sm text-fg"
              labelClassName="text-sm font-medium text-fg"
            />
          </div>
        </div>

        {form.role !== user.role ? (
          <div className="mt-6">
            <p className="rounded-md border border-warning-border bg-warning-subtle px-4 py-3 text-sm text-warning font-medium">
              Changing this user's role will sign them out of every active session immediately.
            </p>
          </div>
        ) : null}

        {errorMessage ? <p className="mt-4 text-sm text-danger">{errorMessage}</p> : null}

        <hr className="border-t border-stroke my-6 -mx-6" />

        <div className="flex items-center justify-between">
          <div className="flex flex-col text-[12px] font-normal text-fg-muted leading-[28px]">
            <div>Date Added: {formatShortDateTime(user.created_at ?? null)}</div>
            <div>Last Changes: {formatShortDateTime(user.updated_at ?? null)}</div>
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
