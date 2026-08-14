import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

export function Switch({
  checked,
  disabled,
  label,
  onChange,
}: {
  checked: boolean
  disabled?: boolean
  /** Accessible name. A bare toggle in a table row has no visible label. */
  label?: string
  onChange?: () => void
}) {
  return (
    <button
      type="button"
      onClick={onChange}
      disabled={disabled}
      aria-label={label}
      aria-pressed={checked}
      className={cn(
        "relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-150",
        focusRing,
        checked ? "bg-primary" : "bg-surface-3",
        disabled ? "cursor-not-allowed opacity-60" : "",
      )}
    >
      <span
        className={cn(
          "inline-block h-3.5 w-3.5 transform rounded-full bg-fg-on-primary transition-transform",
          checked ? "translate-x-4" : "translate-x-1",
        )}
      />
    </button>
  )
}
