import { cn } from "@/utils/cn"

export function Switch({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean
  disabled?: boolean
  onChange?: () => void
}) {
  return (
    <button
      type="button"
      onClick={onChange}
      disabled={disabled}
      aria-pressed={checked}
      className={cn(
        "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
        checked ? "bg-white" : "bg-[#3f3f46]",
        disabled ? "cursor-not-allowed opacity-60" : "",
      )}
    >
      <span
        className={cn(
          "inline-block h-3.5 w-3.5 transform rounded-full bg-[#18181b] transition-transform",
          checked ? "translate-x-4" : "translate-x-1",
        )}
      />
    </button>
  )
}
