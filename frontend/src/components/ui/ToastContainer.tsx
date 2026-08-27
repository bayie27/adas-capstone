import { useEffect, useRef, useState } from "react"
import {
  RiAlertFill,
  RiCheckboxCircleFill,
  RiCloseLine,
  RiErrorWarningFill,
  RiInformationFill,
} from "@remixicon/react"

import { useToastStore, type ToastItem, type ToastTone } from "@/store/useToastStore"
import { cn } from "@/utils/cn"

const TONE_ICONS: Record<ToastTone, typeof RiCheckboxCircleFill> = {
  success: RiCheckboxCircleFill,
  error: RiErrorWarningFill,
  warning: RiAlertFill,
  info: RiInformationFill,
}

const TONE_STYLES: Record<ToastTone, { border: string; iconColor: string; bgBadge: string }> = {
  success: {
    border: "border-success-border/60",
    iconColor: "text-success",
    bgBadge: "bg-success-subtle",
  },
  error: {
    border: "border-danger-border/60",
    iconColor: "text-danger",
    bgBadge: "bg-danger-subtle",
  },
  warning: {
    border: "border-warning-border/60",
    iconColor: "text-warning",
    bgBadge: "bg-warning-subtle",
  },
  info: {
    border: "border-stroke-strong",
    iconColor: "text-fg",
    bgBadge: "bg-surface-3",
  },
}

function ToastCard({ toast }: { toast: ToastItem }) {
  const dismissToast = useToastStore((state) => state.dismissToast)
  const duration = toast.duration ?? 4000
  const [isPaused, setIsPaused] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (duration <= 0 || isPaused) return

    timerRef.current = setTimeout(() => {
      dismissToast(toast.id)
    }, duration)

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [duration, isPaused, toast.id, dismissToast])

  const toneStyle = TONE_STYLES[toast.tone]
  const IconComponent = TONE_ICONS[toast.tone]

  return (
    <div
      role={toast.tone === "error" ? "alert" : "status"}
      aria-live={toast.tone === "error" ? "assertive" : "polite"}
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      className={cn(
        "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border p-3.5 shadow-xl backdrop-blur-md transition-all",
        "animate-toast-in bg-surface-1/95 text-fg",
        toneStyle.border,
      )}
    >
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-md",
          toneStyle.bgBadge,
          toneStyle.iconColor,
        )}
      >
        <IconComponent size={18} aria-hidden />
      </div>

      <div className="min-w-0 flex-1 pt-0.5">
        {toast.title ? (
          <h4 className="text-xs font-bold uppercase tracking-wider text-fg">{toast.title}</h4>
        ) : null}
        <p className="text-xs font-medium leading-relaxed text-fg-body">{toast.message}</p>
      </div>

      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={() => dismissToast(toast.id)}
        className="shrink-0 rounded p-1 text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
      >
        <RiCloseLine size={16} aria-hidden />
      </button>
    </div>
  )
}

/**
 * Mounts at high z-index (z-[9990]) to display non-blocking action feedback toasts
 * across the application. Stays beneath GlobalAlerts (z-9999).
 */
export function ToastContainer() {
  const toasts = useToastStore((state) => state.toasts)

  if (toasts.length === 0) return null

  return (
    <div aria-label="Notifications" className="flex max-w-sm flex-col gap-2.5 pointer-events-none">
      {toasts.map((item) => (
        <ToastCard key={item.id} toast={item} />
      ))}
    </div>
  )
}
