import { useState, useRef, useEffect } from "react"
import { RiArrowDownSLine, RiCheckLine } from "@remixicon/react"
import { cn } from "@/utils/cn"
import { SearchInput } from "@/components/ui/SearchInput"

type FilterOption<T extends string> = {
  value: T
  label: string
}

interface FilterSelectProps<T extends string> {
  value: T
  options: FilterOption<T>[]
  onChange: (value: T) => void
  className?: string
  disabled?: boolean
  ariaLabel?: string
  enableSearch?: boolean
  direction?: "down" | "up"
}

export function FilterSelect<T extends string>({
  value,
  options,
  onChange,
  className,
  disabled,
  ariaLabel,
  enableSearch = false,
  direction = "down",
}: FilterSelectProps<T>) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleOutsideClick)
    }
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick)
    }
  }, [isOpen])

  const filteredOptions = enableSearch
    ? options.filter((opt) => opt.label.toLowerCase().includes(searchQuery.toLowerCase()))
    : options

  const selectedOption = options.find((opt) => opt.value === value)
  const displayLabel = selectedOption ? selectedOption.label : "Select..."

  return (
    <div className="relative inline-block" ref={containerRef}>
      <button
        type="button"
        disabled={disabled}
        aria-label={ariaLabel}
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "inline-flex h-9 items-center justify-between gap-2 rounded border border-stroke bg-canvas px-4 py-2 shadow-md",
          "text-sm font-normal text-fg transition-colors duration-150",
          disabled
            ? "cursor-not-allowed opacity-60"
            : "hover:border-stroke-strong focus:outline-none focus-visible:ring-1 focus-visible:ring-fg",
          className,
        )}
      >
        <span className="truncate">{displayLabel}</span>
        <RiArrowDownSLine size={16} className="shrink-0 text-fg" aria-hidden="true" />
      </button>

      {isOpen && (
        <div
          className={cn(
            "absolute left-0 w-max min-w-full z-50 rounded border border-stroke bg-canvas shadow-md overflow-hidden",
            direction === "up" ? "bottom-full mb-1" : "top-full mt-1",
          )}
        >
          {enableSearch && (
            <div className="p-2 border-b border-stroke bg-surface-1">
              <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Search..." />
            </div>
          )}
          <ul className="custom-scrollbar max-h-[300px] overflow-y-auto py-1 m-0 list-none">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option) => (
                <li
                  key={option.value}
                  className="flex items-center justify-between px-4 py-2 cursor-pointer text-sm text-fg hover:bg-surface-1"
                  onClick={() => {
                    onChange(option.value)
                    setIsOpen(false)
                    setSearchQuery("")
                  }}
                >
                  <span className="truncate pr-4">{option.label}</span>
                  {value === option.value && (
                    <RiCheckLine size={14} className="text-fg shrink-0" aria-hidden="true" />
                  )}
                </li>
              ))
            ) : (
              <li className="px-4 py-3 text-center text-sm text-fg-muted">No results found</li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
}
