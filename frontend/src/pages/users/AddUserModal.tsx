import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"

import { Modal } from "@/components/ui/Modal"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { createUser } from "@/services/users"
import type { ApiUserRole } from "@/types/auth"
import type { CreateUserInput, UserRecord } from "@/types/users"
import { getApiErrorMessage } from "@/utils/api"
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
                <label className="flex cursor-pointer items-center gap-2 text-xs text-fg-body">
                  <input
                    type="radio"
                    name="role"
                    className="accent-white"
                    checked={form.role === "Admin"}
                    onChange={() => updateField("role", "Admin")}
                  />
                  Administrator
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-xs text-fg-body">
                  <input
                    type="radio"
                    name="role"
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
                className="w-full rounded-md border border-stroke bg-surface-1 px-3 py-2 text-sm text-fg placeholder-fg-muted focus:border-stroke-strong focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold text-fg-body">Last Name</label>
              <input
                type="text"
                value={form.last_name}
                onChange={(event) => updateField("last_name", event.target.value)}
                className="w-full rounded-md border border-stroke bg-surface-1 px-3 py-2 text-sm text-fg placeholder-fg-muted focus:border-stroke-strong focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold text-fg-body">Username</label>
              <input
                type="text"
                value={form.username}
                onChange={(event) => updateField("username", event.target.value)}
                className="w-full rounded-md border border-stroke bg-surface-1 px-3 py-2 text-sm text-fg placeholder-fg-muted focus:border-stroke-strong focus:outline-none"
              />
            </div>
          </div>
        </div>

        <div className="h-px w-full bg-surface-3" />

        <div className="grid grid-cols-[100px_1fr] gap-4">
          <div className="pt-1 text-xs font-semibold text-fg-body">Enter Password</div>
          <div className="grid grid-cols-2 gap-4">
            <PasswordInput
              label="Password"
              value={form.password}
              onChange={(value) => updateField("password", value)}
            />
            <PasswordInput
              label="Confirm Password"
              value={form.confirm_password}
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
