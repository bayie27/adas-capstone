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
import { getApiError, getApiErrorMessage } from "@/api/client"
import { getFieldValidationMessage } from "@/utils/apiFieldErrors"
import { validateNewPassword, validatePasswordConfirmation } from "@/utils/passwordValidation"

type CreateUserFormState = {
  first_name: string
  last_name: string
  username: string
  role: ApiUserRole
  password: string
  confirm_password: string
}

type PasswordFieldErrors = Partial<Record<"password" | "confirm_password", string>>

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
  const [fieldErrors, setFieldErrors] = useState<PasswordFieldErrors>({})

  const mutation = useMutation({
    mutationFn: createUser,
    onSuccess,
  })

  function updateField<K extends keyof CreateUserFormState>(
    field: K,
    value: CreateUserFormState[K],
  ) {
    setValidationError(null)
    if (field === "password" || field === "confirm_password") {
      setFieldErrors((current) => ({ ...current, [field]: undefined }))
    }
    mutation.reset()
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setValidationError(null)

    const trimmedFirstName = form.first_name.trim()
    const trimmedLastName = form.last_name.trim()
    const trimmedUsername = form.username.trim()

    if (!trimmedFirstName || !trimmedLastName || !trimmedUsername) {
      setValidationError("All user fields are required.")
      return
    }

    const errors: PasswordFieldErrors = {
      password: validateNewPassword(form.password),
      confirm_password: validatePasswordConfirmation(form.password, form.confirm_password),
    }
    setFieldErrors(errors)
    if (Object.values(errors).some(Boolean)) return

    const payload: CreateUserInput = {
      first_name: trimmedFirstName,
      last_name: trimmedLastName,
      username: trimmedUsername,
      role: form.role,
      password: form.password,
    }

    mutation.mutate(payload)
  }

  // The server-side strength check should never fire once the client-side
  // one above agrees with it, but it's the final word — attribute a 422 that
  // still names password to that field rather than a generic banner.
  const apiPasswordError = mutation.isError
    ? getFieldValidationMessage(mutation.error, "password")
    : undefined
  const passwordError = fieldErrors.password ?? apiPasswordError

  // create_user (routes/users.py) answers a duplicate with a plain 400 —
  // the one collision this form can have is on username, so that's where it
  // belongs rather than a banner disconnected from the field.
  const usernameError =
    mutation.isError && getApiError(mutation.error)?.status === 400
      ? getApiErrorMessage(mutation.error, "Username already taken.")
      : undefined

  const errorMessage =
    validationError ??
    (mutation.isError && !apiPasswordError && !usernameError
      ? getApiErrorMessage(mutation.error, "Unable to create user.")
      : null)

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Add User"
      subtitle="Create a new user & assign an access role"
      icon={
        <div className="flex h-[64px] w-[64px] shrink-0 items-center justify-center rounded-full border border-stroke">
          <RiUser3Line size={28} className="text-fg" />
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
              className="text-sm text-fg"
              labelClassName="text-sm font-medium text-fg"
            />
            <Input
              label="Last Name"
              placeholder="Doe"
              value={form.last_name}
              disabled={mutation.isPending}
              onChange={(event) => updateField("last_name", event.target.value)}
              className="text-sm text-fg"
              labelClassName="text-sm font-medium text-fg"
            />
            <Input
              label="Username"
              placeholder="jdoe"
              value={form.username}
              disabled={mutation.isPending}
              error={usernameError}
              onChange={(event) => updateField("username", event.target.value)}
              className="text-sm text-fg"
              labelClassName="text-sm font-medium text-fg"
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
                error={passwordError}
                onChange={(value) => updateField("password", value)}
                inputClassName="text-sm text-fg"
                labelClassName="text-sm font-medium text-fg"
              />
              <PasswordInput
                label="Confirm Password"
                value={form.confirm_password}
                disabled={mutation.isPending}
                error={fieldErrors.confirm_password}
                onChange={(value) => updateField("confirm_password", value)}
                inputClassName="text-sm text-fg"
                labelClassName="text-sm font-medium text-fg"
              />
            </div>
            <div className="text-[12px] font-normal text-fg-muted">
              Must be at least 8 characters long and contain at least 1 number.
            </div>
          </div>
        </div>

        {errorMessage ? <p className="mt-4 text-xs text-danger">{errorMessage}</p> : null}

        <hr className="border-t border-stroke my-6 -mx-6" />

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
      </form>
    </Modal>
  )
}
