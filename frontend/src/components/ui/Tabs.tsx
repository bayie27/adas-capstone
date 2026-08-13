import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

/**
 * The tab switcher the frames draw in two shapes:
 *
 * - `chip`  Detections' Ongoing / Logs — a rounded-md chip, selected state
 *           filled with --color-surface-2 on a --color-stroke border (§2.8).
 * - `pill`  System Health's 48h / 30d range switcher — the same states at
 *           --radius-full.
 *
 * Uses the WAI-ARIA tablist pattern with roving arrow-key selection, because
 * a switcher built from bare buttons is unreachable in the way an operator
 * under load actually drives the console.
 */
export interface TabItem<T extends string> {
  value: T
  label: string
}

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  variant = "chip",
  label,
  className,
}: {
  items: TabItem<T>[]
  value: T
  onChange: (value: T) => void
  variant?: "chip" | "pill"
  /** Accessible name for the tablist, e.g. "Detection views". */
  label: string
  className?: string
}) {
  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const index = items.findIndex((item) => item.value === value)
    if (index === -1) return

    let next: number
    if (event.key === "ArrowRight") next = (index + 1) % items.length
    else if (event.key === "ArrowLeft") next = (index - 1 + items.length) % items.length
    else if (event.key === "Home") next = 0
    else if (event.key === "End") next = items.length - 1
    else return

    event.preventDefault()
    onChange(items[next].value)
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cn("flex items-center gap-2", className)}
    >
      {items.map((item) => {
        const selected = item.value === value
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.value)}
            className={cn(
              "px-4 py-1.5 text-caption font-medium transition-colors duration-150",
              variant === "pill" ? "rounded-full" : "rounded-md",
              selected
                ? "border border-stroke bg-surface-2 text-fg"
                : "border border-transparent text-fg-muted hover:text-fg-body",
              focusRing,
            )}
          >
            {item.label}
          </button>
        )
      })}
    </div>
  )
}
