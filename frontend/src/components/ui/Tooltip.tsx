import { useState, useId, useRef, useEffect, type ReactNode, type KeyboardEvent } from "react"
import { cn } from "@/utils/cn"

export interface TooltipProps {
  content: ReactNode
  children: ReactNode
  side?: "top" | "bottom" | "left" | "right"
  align?: "start" | "center" | "end"
  className?: string
  /** Delay in milliseconds before closing on mouse leave (default: 250ms) */
  closeDelayMs?: number
}

const SIDE_CLASSES: Record<"top" | "bottom" | "left" | "right", string> = {
  top: "bottom-full mb-2 before:absolute before:top-full before:left-0 before:right-0 before:h-2 before:content-['']",
  bottom:
    "top-full mt-2 before:absolute before:bottom-full before:left-0 before:right-0 before:h-2 before:content-['']",
  left: "right-full mr-2 before:absolute before:left-full before:top-0 before:bottom-0 before:w-2 before:content-['']",
  right:
    "left-full ml-2 before:absolute before:right-full before:top-0 before:bottom-0 before:w-2 before:content-['']",
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
  closeDelayMs = 250,
}: TooltipProps) {
  const [isOpen, setIsOpen] = useState(false)
  const tooltipId = useId()
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearCloseTimeout = () => {
    if (closeTimeoutRef.current) {
      clearTimeout(closeTimeoutRef.current)
      closeTimeoutRef.current = null
    }
  }

  const openTooltip = () => {
    clearCloseTimeout()
    setIsOpen(true)
  }

  const closeTooltip = (immediate = false) => {
    clearCloseTimeout()
    if (immediate) {
      setIsOpen(false)
    } else {
      closeTimeoutRef.current = setTimeout(() => {
        setIsOpen(false)
        closeTimeoutRef.current = null
      }, closeDelayMs)
    }
  }

  useEffect(() => {
    return () => {
      clearCloseTimeout()
    }
  }, [])

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      closeTooltip(true)
    }
  }

  const handleBlur = (e: React.FocusEvent) => {
    if (
      !e.relatedTarget ||
      !(e.relatedTarget instanceof Node) ||
      !e.currentTarget.contains(e.relatedTarget)
    ) {
      closeTooltip(true)
    }
  }

  const handleMouseLeave = (e: React.MouseEvent) => {
    if (
      !e.relatedTarget ||
      !(e.relatedTarget instanceof Node) ||
      !e.currentTarget.contains(e.relatedTarget)
    ) {
      closeTooltip(false)
    }
  }

  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={openTooltip}
      onMouseLeave={handleMouseLeave}
      onFocus={openTooltip}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
      aria-describedby={isOpen ? tooltipId : undefined}
    >
      {children}
      {isOpen && (
        <span
          id={tooltipId}
          role="tooltip"
          onMouseEnter={openTooltip}
          onMouseLeave={handleMouseLeave}
          className={cn(
            "pointer-events-auto absolute z-50 w-72 max-w-xs whitespace-normal rounded-md border border-stroke bg-surface-3 px-3 py-2 text-xs font-normal leading-relaxed text-fg-body shadow-lg",
            "animate-alert-fade-in",
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
