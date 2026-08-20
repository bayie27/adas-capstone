import { RiSearchLine } from "@remixicon/react"
import { cn } from "@/utils/cn"

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
    <div
      className={cn(
        "flex items-center h-9 px-4 py-2 gap-2 bg-canvas border border-stroke rounded shadow-md",
        "focus-within:ring-1 focus-within:ring-stroke-strong",
        "transition-colors duration-150 w-60",
      )}
    >
      <RiSearchLine className="w-4 h-4 text-fg-muted shrink-0" />
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="bg-transparent outline-none w-full text-xs font-normal text-fg placeholder:text-fg-muted disabled:cursor-not-allowed disabled:opacity-60"
      />
    </div>
  )
}
