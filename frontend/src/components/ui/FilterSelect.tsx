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
}

export function FilterSelect<T extends string>({ value, options, onChange }: FilterSelectProps<T>) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
        className={cn(
          "appearance-none rounded-md border border-stroke bg-surface-1 px-3 py-1.5 pr-8 text-xs text-fg-body",
          "transition-colors duration-150 focus:border-stroke-strong",
          "disabled:cursor-not-allowed disabled:opacity-60",
          focusRing,
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
