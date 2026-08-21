import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { RiUser3Line } from "@remixicon/react"

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
    <Modal isOpen onClose={onClose} className="bg-surface-2 p-1 pt-7 sm:max-w-[700px]">
      <form onSubmit={handleSubmit} className="flex flex-col">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4 mb-6">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border border-stroke-strong">
              <RiUser3Line size={28} className="text-fg-body" />
            </div>
            <div className="flex flex-col">
              <h3 className="text-[20px] font-semibold text-fg-body leading-[32px]">Add User</h3>
              <p className="text-[14px] font-normal text-fg-muted leading-[28px]">
                Create a new user & assign an access role
              </p>
            </div>
          </div>
        </div>
        <hr className="border-t border-stroke-strong mb-6 -mx-7" />

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
                    "flex flex-1 cursor-pointer items-center gap-2 text-sm font-normal text-fg",
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
            </div>

            <Input
              label="First Name"
              placeholder="John"
              value={form.first_name}
              disabled={mutation.isPending}
              onChange={(event) => updateField("first_name", event.target.value)}
              className="border-stroke-strong bg-transparent text-fg-muted text-[14px] h-10"
              labelClassName="text-[14px] font-medium text-fg leading-[28px]"
            />
            <Input
              label="Last Name"
              placeholder="Doe"
              value={form.last_name}
              disabled={mutation.isPending}
              onChange={(event) => updateField("last_name", event.target.value)}
              className="border-stroke-strong bg-transparent text-fg-muted text-[14px] h-10"
              labelClassName="text-[14px] font-medium text-fg leading-[28px]"
            />
            <Input
              label="Username"
              placeholder="jdoe"
              value={form.username}
              disabled={mutation.isPending}
              onChange={(event) => updateField("username", event.target.value)}
              className="border-stroke-strong bg-transparent text-fg-muted text-[14px] h-10"
              labelClassName="text-[14px] font-medium text-fg leading-[28px]"
            />
          </div>
        </div>

        <hr className="border-t border-stroke-strong my-6 -mx-7" />

        <div className="grid grid-cols-[150px_1fr] gap-x-8 gap-y-6">
          <div className="text-base font-medium text-fg">Enter Password</div>
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4">
              <PasswordInput
                label="Password"
                value={form.password}
                disabled={mutation.isPending}
                onChange={(value) => updateField("password", value)}
                inputClassName="border-stroke-strong bg-transparent text-fg-muted text-[14px] h-10"
                labelClassName="text-[14px] font-medium text-fg leading-[28px]"
              />
              <PasswordInput
                label="Confirm Password"
                value={form.confirm_password}
                disabled={mutation.isPending}
                onChange={(value) => updateField("confirm_password", value)}
                inputClassName="border-stroke-strong bg-transparent text-fg-muted text-[14px] h-10"
                labelClassName="text-[14px] font-medium text-fg leading-[28px]"
              />
            </div>
            <div className="text-[14px] font-normal text-fg-muted leading-[28px]">
              Must be at least 8 characters long and contain at least 1 number.
            </div>
          </div>
        </div>

        {errorMessage ? <p className="mt-4 text-xs text-danger">{errorMessage}</p> : null}

        <hr className="border-t border-stroke-strong my-6 -mx-7" />

        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            className="border-stroke-strong text-[14px] font-medium text-fg px-4 py-2"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            className="bg-fg-body text-surface-2 hover:opacity-90 text-[14px] font-medium px-4 py-2"
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
