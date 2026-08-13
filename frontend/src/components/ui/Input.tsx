import { useId, type InputHTMLAttributes, type ReactNode } from "react"

import { cn } from "@/utils/cn"
import { disabledTreatment, focusRing } from "@/components/ui/Button"

/**
 * The `Input/With Label` component from the Figma frames: a caption-sized
 * label above a 40px control (§2.3), with an optional trailing slot for the
 * affordances the frames draw inside the field — the password eye, a unit
 * suffix.
 *
 * States per §2.8: the border lifts to --color-stroke-strong on focus (which
 * the old inline markup approximated with `focus:border-[#555]`), the shared
 * focus-visible ring applies, disabled is opacity-60, and an `error` message
 * switches the border to --color-danger and renders the message below.
 */
interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: string
  /** Renders below the field in --color-danger and marks the field invalid. */
  error?: string
  /** Renders below the field in --color-fg-muted when there is no error. */
  hint?: string
  /** Inside the field, right-aligned — the password eye, for instance. */
  trailing?: ReactNode
  labelClassName?: string
}

export function Input({
  label,
  error,
  hint,
  trailing,
  className,
  labelClassName,
  id,
  disabled,
  ...rest
}: InputProps) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const messageId = `${inputId}-message`

  return (
    <div>
      {label ? (
        <label
          htmlFor={inputId}
          className={cn(
            "mb-2 block text-caption font-semibold text-fg-body",
            disabled && "opacity-60",
            labelClassName,
          )}
        >
          {label}
        </label>
      ) : null}

      <div className="relative">
        <input
          id={inputId}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={error || hint ? messageId : undefined}
          className={cn(
            "h-10 w-full rounded-md border bg-surface-1 px-4 text-secondary text-fg",
            "placeholder:text-fg-muted transition-colors duration-150",
            error ? "border-danger" : "border-border focus:border-stroke-strong",
            trailing && "pr-10",
            focusRing,
            disabledTreatment,
            className,
          )}
          {...rest}
        />
        {trailing ? (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center">
            {trailing}
          </span>
        ) : null}
      </div>

      {error ? (
        <p id={messageId} className="mt-1.5 text-caption text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={messageId} className="mt-1.5 text-caption text-fg-muted">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
