import { RiSearchLine } from "@remixicon/react"
import { cn } from "@/utils/cn"

export function SearchInput({
  value,
  onChange,
  placeholder,
  maxLength,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  /** Caps what the user can type at the DOM level, so a search that a
   * backend query-param limit would otherwise reject with a 422 is never
   * typeable in the first place. Optional and unset by default; existing
   * callers are unaffected. */
  maxLength?: number
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
        maxLength={maxLength}
        className="bg-transparent outline-none w-full text-sm font-normal text-fg placeholder:text-fg-muted disabled:cursor-not-allowed disabled:opacity-60"
      />
    </div>
  )
}
