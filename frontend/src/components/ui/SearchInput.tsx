import { RiSearchLine } from "@remixicon/react"
import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

export function SearchInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}) {
  return (
    <div className="relative">
      <RiSearchLine size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted" />
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={cn(
          "w-60 rounded-md border border-stroke bg-surface-1 py-1.5 pl-8 pr-4 text-xs text-fg",
          "transition-colors duration-150 placeholder:text-fg-muted focus:border-stroke-strong",
          "disabled:cursor-not-allowed disabled:opacity-60",
          focusRing,
        )}
      />
    </div>
  )
}
