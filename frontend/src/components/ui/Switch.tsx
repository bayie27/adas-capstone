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
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors duration-150",
        focusRing,
        checked ? "bg-primary" : "bg-surface-3",
        disabled ? "cursor-not-allowed opacity-60" : "",
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 transform rounded-full transition-transform",
          // fg-on-primary (near-black) is legible on the light `checked`
          // track, but the same dark thumb on the dark `surface-3` track
          // read as invisible — the unchecked thumb needs the light `fg`
          // token instead.
          checked ? "translate-x-4 bg-fg-on-primary" : "translate-x-0 bg-fg",
        )}
      />
    </button>
  )
}
