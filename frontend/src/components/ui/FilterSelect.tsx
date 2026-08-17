import { RiArrowRightSLine } from "@remixicon/react"
import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

type FilterOption<T extends string> = {
  value: T
  label: string
}

interface FilterSelectProps<T extends string> {
  value: T
  options: FilterOption<T>[]
  onChange: (value: T) => void
  /** Additional classes on the `<select>` itself -- e.g. `w-full` for a form
   * field rather than this component's default toolbar-compact width. */
  className?: string
  disabled?: boolean
  /** For a select with no associated visible `<label>` -- e.g. a toolbar
   * control identified only by an icon or by text that isn't a `<label
   * for>`, like PaginationFooter's "Items per page". */
  ariaLabel?: string
}

export function FilterSelect<T extends string>({
  value,
  options,
  onChange,
  className,
  disabled,
  ariaLabel,
}: FilterSelectProps<T>) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
        disabled={disabled}
        aria-label={ariaLabel}
        className={cn(
          "appearance-none rounded-md border border-stroke bg-surface-1 px-3 py-1.5 pr-8 text-xs text-fg-body",
          "transition-colors duration-150 focus:border-stroke-strong",
          "disabled:cursor-not-allowed disabled:opacity-60",
          focusRing,
          className,
        )}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <RiArrowRightSLine
        size={13}
        className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-fg-muted"
      />
    </div>
  )
}
