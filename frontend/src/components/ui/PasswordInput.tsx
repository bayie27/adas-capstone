import { useState } from "react"

import { cn } from "@/utils/cn"
import { Input } from "@/components/ui/Input"
import { focusRing } from "@/components/ui/Button"
import { RiEyeLine, RiEyeOffLine } from "@remixicon/react"

/**
 * Label + password field + eye-toggle, now built on `Input` so there is one
 * field implementation rather than two. Owns its own visibility state (pure
 * presentation — no parent needs to read it). Defaults `autoComplete` to
 * "new-password" so browsers don't autofill an admin's own password into
 * "reset user password" forms.
 *
 * The className overrides below reproduce this component's existing geometry
 * exactly, so rebuilding it on `Input` changes no pixel on Login or the
 * password modals. They are the seam: the screen phases drop them and the
 * field inherits `Input`'s 40px §2.3 control height.
 */
export function PasswordInput({
  label,
  value,
  onChange,
  autoComplete = "new-password",
  placeholder,
  labelClassName,
  inputClassName,
  toggleClassName,
  iconSize = 14,
  disabled,
  error,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  autoComplete?: string
  placeholder?: string
  labelClassName?: string
  inputClassName?: string
  toggleClassName?: string
  iconSize?: number
  disabled?: boolean
  error?: string
}) {
  const [visible, setVisible] = useState(false)

  return (
    <Input
      label={label}
      type={visible ? "text" : "password"}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      autoComplete={autoComplete}
      placeholder={placeholder}
      disabled={disabled}
      error={error}
      labelClassName={cn("text-[11px]", labelClassName)}
      className={cn(
        "h-auto border-stroke px-3 py-2 text-sm",
        error && "border-danger",
        inputClassName,
      )}
      trailing={
        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          disabled={disabled}
          aria-label={visible ? "Hide password" : "Show password"}
          className={cn(
            "rounded-sm text-fg-muted transition-colors duration-150 hover:text-fg",
            "disabled:cursor-not-allowed disabled:opacity-60",
            focusRing,
            toggleClassName,
          )}
        >
          {visible ? <RiEyeLine size={iconSize} /> : <RiEyeOffLine size={iconSize} />}
        </button>
      }
    />
  )
}
