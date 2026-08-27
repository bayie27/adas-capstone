import { RiCloseLine } from "@remixicon/react"
import { cn } from "@/utils/cn"

export function ClearFiltersButton({
  onClick,
  className,
}: {
  onClick: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex h-9 items-center gap-2 rounded border border-stroke bg-canvas px-4 py-2 shadow-md",
        "text-sm font-normal text-fg transition-colors duration-150 hover:bg-surface-1",
        "focus:outline-none focus-visible:ring-1 focus-visible:ring-fg",
        className,
      )}
    >
      <RiCloseLine size={16} className="shrink-0 text-fg" aria-hidden="true" />
      Clear
    </button>
  )
}
