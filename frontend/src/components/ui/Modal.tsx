import { RiCloseLine } from "@remixicon/react"
import { useOverlayBehavior } from "@/hooks/useOverlayBehavior"
import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  subtitle?: string
  icon?: React.ReactNode
  children: React.ReactNode
  className?: string
  hideClose?: boolean
  closeOnBackdrop?: boolean
  /**
   * Overrides the fixed positioning layer, for the one overlay that must
   * outrank every other: the HITL accident alarm. An alert firing while an
   * operator has an incident open has to land on top of it, not behind it.
   */
  overlayClassName?: string
  /**
   * Overrides the backdrop. §2.6 gives the HITL alert a heavier scrim
   * (`--color-backdrop-alert`, 0.70) than an ordinary modal (0.60) so it
   * reads as more blocking.
   */
  backdropClassName?: string
  /**
   * Optional wrapper className or outer content rendered in the modal's centering
   * container outside the dialog card (e.g. navigation controls, badges).
   */
  wrapperClassName?: string
  outerContent?: React.ReactNode
}

export function Modal({
  isOpen,
  onClose,
  title,
  subtitle,
  icon,
  children,
  className,
  hideClose,
  closeOnBackdrop = true,
  overlayClassName,
  backdropClassName,
  role = "dialog",
  ariaLabel,
  wrapperClassName,
  outerContent,
}: ModalProps) {
  const dialogRef = useOverlayBehavior(isOpen, onClose)

  if (!isOpen) return null

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-auto",
        overlayClassName,
      )}
    >
      <div
        className={cn(
          "absolute inset-0 bg-backdrop transition-opacity pointer-events-auto cursor-pointer",
          backdropClassName,
        )}
        onClick={closeOnBackdrop ? onClose : undefined}
      />

      <div className={cn("relative flex flex-col items-center max-w-full", wrapperClassName)}>
        <div
          ref={dialogRef}
          role={role}
          aria-modal="true"
          aria-label={title ?? ariaLabel}
          tabIndex={-1}
          className={cn(
            "relative bg-surface-1 border border-stroke rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200",
            className,
          )}
        >
          {(title || icon) && (
            <div className="px-6 pt-6 pb-4 flex items-start justify-between">
              <div className="flex items-start gap-4">
                {icon}
                <div>
                  {title && (
                    <h3 className="text-lg font-semibold text-fg leading-tight">{title}</h3>
                  )}
                  {subtitle && (
                    <p className="text-sm text-fg-muted mt-1 leading-relaxed">{subtitle}</p>
                  )}
                </div>
              </div>
              {!hideClose && (
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close dialog"
                  className={cn(
                    "rounded-sm text-fg-muted transition-colors duration-150 hover:text-fg",
                    focusRing,
                  )}
                >
                  <RiCloseLine size={20} />
                </button>
              )}
            </div>
          )}

          {!title && !icon && !hideClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close dialog"
              className={cn(
                "absolute right-4 top-4 z-10 rounded-sm text-fg-muted transition-colors duration-150 hover:text-fg",
                focusRing,
              )}
            >
              <RiCloseLine size={20} />
            </button>
          )}

          <div className="px-6 pb-6">{children}</div>
        </div>
        {outerContent}
      </div>
    </div>
  )
}
