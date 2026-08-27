import { RiCloseLine } from "@remixicon/react"
import { useOverlayBehavior } from "@/hooks/useOverlayBehavior"
import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

interface SidePanelProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  subtitle?: string
  children: React.ReactNode
  className?: string
}

/**
 * A right-anchored drawer, hand-rolled on the same tokens as Modal.
 *
 * Deliberately not shadcn/Radix (DT-6): this frontend has no components.json,
 * no Radix and no CVA, so adding one would import a whole second component
 * convention alongside the existing one for a single drawer.
 *
 * z-[9000] sits above Modal (z-50) but below GlobalAlerts (z-9999) — when a
 * real alert fires mid-demo, the alarm modal is the thing to see.
 */
export function SidePanel({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  className,
}: SidePanelProps) {
  const dialogRef = useOverlayBehavior(isOpen, onClose)

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-[9000] pointer-events-auto">
      <div
        data-testid="side-panel-backdrop"
        className="absolute inset-0 bg-backdrop transition-opacity pointer-events-auto cursor-pointer"
        onClick={onClose}
      />

      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          "absolute right-0 top-0 h-full w-[420px] max-w-full overflow-y-auto pointer-events-auto",
          "bg-surface-1 border-l border-stroke shadow-2xl",
          "animate-in slide-in-from-right duration-200",
          className,
        )}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-stroke bg-surface-1 px-5 py-4">
          <div>
            {title && <h3 className="text-base font-semibold leading-tight text-fg">{title}</h3>}
            {subtitle && <p className="mt-1 text-xs leading-relaxed text-fg-muted">{subtitle}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className={cn(
              "rounded-sm text-fg-muted transition-colors duration-150 hover:text-fg",
              focusRing,
            )}
          >
            <RiCloseLine size={20} />
          </button>
        </div>

        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  )
}
