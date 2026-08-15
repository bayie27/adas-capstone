import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Modal } from "@/components/ui/Modal"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { createUser } from "@/api/users"
import { cn } from "@/utils/cn"
import type { ApiUserRole } from "@/api/auth"
import type { CreateUserInput, UserRecord } from "@/api/users"
import { getApiErrorMessage } from "@/api/client"
import { RiUserAddLine } from "@remixicon/react"

type CreateUserFormState = {
  first_name: string
  last_name: string
  username: string
  role: ApiUserRole
  password: string
  confirm_password: string
}

const EMPTY_FORM: CreateUserFormState = {
  first_name: "",
  last_name: "",
  username: "",
  role: "Operator",
  password: "",
  confirm_password: "",
}

interface AddUserModalProps {
  onClose: () => void
  onSuccess: (user: UserRecord) => void
}

export function AddUserModal({ onClose, onSuccess }: AddUserModalProps) {
  const [form, setForm] = useState<CreateUserFormState>(EMPTY_FORM)
  const [validationError, setValidationError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: createUser,
    onSuccess,
  })

  function updateField<K extends keyof CreateUserFormState>(
    field: K,
    value: CreateUserFormState[K],
  ) {
    setValidationError(null)
    mutation.reset()
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setValidationError(null)

    const payload: CreateUserInput = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      username: form.username.trim(),
      role: form.role,
      password: form.password,
    }

    if (!payload.first_name || !payload.last_name || !payload.username || !payload.password) {
      setValidationError("All user fields are required.")
      return
    }

    if (form.password !== form.confirm_password) {
      setValidationError("Password confirmation does not match.")
      return
    }

    mutation.mutate(payload)
  }

  const errorMessage =
    validationError ??
    (mutation.isError ? getApiErrorMessage(mutation.error, "Unable to create user.") : null)

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Add User"
      subtitle="Create a new user & assign an access role"
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-stroke-strong bg-transparent">
          <RiUserAddLine size={20} className="text-fg" />
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
                    name="role"
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
                    name="role"
                    className="accent-white"
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

        <div className="h-px w-full bg-surface-3" />

        <div className="grid grid-cols-[100px_1fr] gap-4">
          <div className="pt-1 text-xs font-semibold text-fg-body">Enter Password</div>
          <div className="grid grid-cols-2 gap-4">
            <PasswordInput
              label="Password"
              value={form.password}
              disabled={mutation.isPending}
              onChange={(value) => updateField("password", value)}
            />
            <PasswordInput
              label="Confirm Password"
              value={form.confirm_password}
              disabled={mutation.isPending}
              onChange={(value) => updateField("confirm_password", value)}
            />
            <div className="col-span-2 mt-1 text-[10px] text-fg-muted">
              Must be at least 8 characters long and contain at least 1 number.
            </div>
          </div>
        </div>

        {errorMessage ? <p className="text-xs text-danger">{errorMessage}</p> : null}

        <div className="h-px w-full bg-surface-3" />

        <div className="flex items-center justify-end gap-3">
          <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button type="submit" isLoading={mutation.isPending} loadingLabel="Saving…">
            Save Changes
          </Button>
        </div>
      </form>
    </Modal>
  )
}
