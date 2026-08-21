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
      className="bg-surface-2 sm:max-w-3xl"
    >
      <form onSubmit={handleSubmit} className="flex flex-col">
        <hr className="border-t border-stroke mb-6 -mx-6" />

        <div className="grid grid-cols-[150px_1fr] gap-x-8 gap-y-6">
          <div className="text-base font-medium text-fg">User</div>
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-8 mb-2">
              <label
                className={cn(
                  "flex cursor-pointer items-center gap-2 text-base font-normal text-fg",
                  mutation.isPending && "cursor-not-allowed opacity-60",
                )}
              >
                <input
                  type="radio"
                  name="role"
                  className="accent-white h-4 w-4 border-fg"
                  checked={form.role === "Admin"}
                  disabled={mutation.isPending}
                  onChange={() => updateField("role", "Admin")}
                />
                Administrator
              </label>
              <label
                className={cn(
                  "flex cursor-pointer items-center gap-2 text-base font-normal text-fg",
                  mutation.isPending && "cursor-not-allowed opacity-60",
                )}
              >
                <input
                  type="radio"
                  name="role"
                  className="accent-white h-4 w-4 border-fg"
                  checked={form.role === "Operator"}
                  disabled={mutation.isPending}
                  onChange={() => updateField("role", "Operator")}
                />
                Operator
              </label>
            </div>

            <Input
              label="First Name"
              value={form.first_name}
              disabled={mutation.isPending}
              onChange={(event) => updateField("first_name", event.target.value)}
              className="text-base text-fg-muted"
              labelClassName="text-base font-medium text-fg"
            />
            <Input
              label="Last Name"
              value={form.last_name}
              disabled={mutation.isPending}
              onChange={(event) => updateField("last_name", event.target.value)}
              className="text-base text-fg-muted"
              labelClassName="text-base font-medium text-fg"
            />
            <Input
              label="Username"
              value={form.username}
              disabled={mutation.isPending}
              onChange={(event) => updateField("username", event.target.value)}
              className="text-base text-fg-muted"
              labelClassName="text-base font-medium text-fg"
            />
          </div>
        </div>

        <hr className="border-t border-stroke my-6 -mx-6" />

        <div className="grid grid-cols-[150px_1fr] gap-x-8 gap-y-6">
          <div className="text-base font-medium text-fg">Enter Password</div>
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4">
              <PasswordInput
                label="Password"
                value={form.password}
                disabled={mutation.isPending}
                onChange={(value) => updateField("password", value)}
                className="text-base text-fg-muted"
                labelClassName="text-base font-medium text-fg"
              />
              <PasswordInput
                label="Confirm Password"
                value={form.confirm_password}
                disabled={mutation.isPending}
                onChange={(value) => updateField("confirm_password", value)}
                className="text-base text-fg-muted"
                labelClassName="text-base font-medium text-fg"
              />
            </div>
            <div className="text-base font-normal text-fg-muted">
              Must be at least 8 characters long and contain at least 1 number.
            </div>
          </div>
        </div>

        {errorMessage ? <p className="mt-4 text-xs text-danger">{errorMessage}</p> : null}

        <hr className="border-t border-stroke my-6 -mx-6" />

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>
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
      </form>
    </Modal>
  )
}
