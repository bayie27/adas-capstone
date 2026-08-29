import { useState, useId, type ReactNode, type KeyboardEvent } from "react"
import { cn } from "@/utils/cn"

export interface TooltipProps {
  content: ReactNode
  children: ReactNode
  side?: "top" | "bottom" | "left" | "right"
  align?: "start" | "center" | "end"
  className?: string
}

const SIDE_CLASSES: Record<"top" | "bottom" | "left" | "right", string> = {
  top: "bottom-full mb-2",
  bottom: "top-full mt-2",
  left: "right-full mr-2",
  right: "left-full ml-2",
}

const ALIGN_CLASSES: Record<
  "top" | "bottom" | "left" | "right",
  Record<"start" | "center" | "end", string>
> = {
  top: {
    start: "left-0",
    center: "left-1/2 -translate-x-1/2",
    end: "right-0",
  },
  bottom: {
    start: "left-0",
    center: "left-1/2 -translate-x-1/2",
    end: "right-0",
  },
  left: {
    start: "top-0",
    center: "top-1/2 -translate-y-1/2",
    end: "bottom-0",
  },
  right: {
    start: "top-0",
    center: "top-1/2 -translate-y-1/2",
    end: "bottom-0",
  },
}

export function Tooltip({
  content,
  children,
  side = "top",
  align = "center",
  className,
}: TooltipProps) {
  const [isOpen, setIsOpen] = useState(false)
  const tooltipId = useId()

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      setIsOpen(false)
    }
  }

  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
      onFocus={() => setIsOpen(true)}
      onBlur={() => setIsOpen(false)}
      onKeyDown={handleKeyDown}
      aria-describedby={isOpen ? tooltipId : undefined}
    >
      {children}
      {isOpen && (
        <span
          id={tooltipId}
          role="tooltip"
          className={cn(
            "pointer-events-none absolute z-50 whitespace-normal rounded-md border border-stroke bg-surface-3 px-2.5 py-1.5 text-xs font-normal text-fg-body shadow-lg",
            "animate-alert-fade-in min-w-[120px] max-w-xs",
            SIDE_CLASSES[side],
            ALIGN_CLASSES[side][align],
            className,
          )}
        >
          {content}
        </span>
      )}
    </span>
  )
}
