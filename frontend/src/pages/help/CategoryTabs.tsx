import { useLayoutEffect, useRef, useState } from "react"
import { RiCompassLine } from "@remixicon/react"

import { focusRing } from "@/components/ui/Button"
import { cn } from "@/utils/cn"
import { categoryIcon } from "./categoryIcons"

function optionKey(option: string): string {
  return option || "all"
}

/**
 * A local chip tablist rather than the shared `Tabs` component: `Tabs`'
 * `label` prop is a plain string, and a category needs an icon alongside it.
 * Styled to match `Tabs`' `chip` variant exactly (§2.8) so it reads as the
 * same control family without widening a shared component's props for one
 * caller.
 */
export function CategoryTabs({
  categories,
  value,
  onChange,
  className,
}: {
  categories: string[]
  value: string
  onChange: (value: string) => void
  className?: string
}) {
  const options = ["", ...categories]
  const buttonRefs = useRef(new Map<string, HTMLButtonElement>())
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null)

  // Measures synchronously before paint, so the indicator never flashes at
  // a stale position for a frame — it just slides to wherever the selected
  // tab actually is, including the first time the category list loads in
  // (which changes every button's position at once).
  useLayoutEffect(() => {
    const el = buttonRefs.current.get(optionKey(value))
    if (el) setIndicator({ left: el.offsetLeft, width: el.offsetWidth })
  }, [value, options.length])

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const index = options.findIndex((option) => option === value)
    if (index === -1) return

    let next: number
    if (event.key === "ArrowRight") next = (index + 1) % options.length
    else if (event.key === "ArrowLeft") next = (index - 1 + options.length) % options.length
    else if (event.key === "Home") next = 0
    else if (event.key === "End") next = options.length - 1
    else return

    event.preventDefault()
    onChange(options[next])
  }

  return (
    <div
      role="tablist"
      aria-label="Help article categories"
      onKeyDown={onKeyDown}
      className={cn(
        "relative inline-flex h-9 flex-wrap items-center justify-start gap-1 rounded-md bg-surface-2 p-1",
        className,
      )}
    >
      {/* One shared sliding indicator instead of each tab drawing its own
          selected-state box, so switching categories reads as one control
          moving rather than two unrelated tabs blinking off/on. */}
      {indicator ? (
        <div
          aria-hidden="true"
          className="absolute top-1 bottom-1 left-0 rounded bg-canvas shadow-sm transition-[transform,width] duration-200 ease-out"
          style={{ transform: `translateX(${indicator.left}px)`, width: indicator.width }}
        />
      ) : null}
      {options.map((option) => {
        const selected = option === value
        const Icon = option ? categoryIcon(option) : RiCompassLine
        return (
          <button
            key={optionKey(option)}
            ref={(el) => {
              if (el) buttonRefs.current.set(optionKey(option), el)
              else buttonRefs.current.delete(optionKey(option))
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(option)}
            className={cn(
              "relative z-10 flex items-center justify-center gap-1.5 rounded px-3 py-1 text-caption font-medium transition-colors duration-150",
              selected ? "text-fg" : "text-fg-muted",
              focusRing,
            )}
          >
            <Icon size={14} className="shrink-0" />
            {option || "All"}
          </button>
        )
      })}
    </div>
  )
}
