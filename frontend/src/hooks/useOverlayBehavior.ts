import { useEffect, useRef } from "react"

/**
 * The behaviour shared by every overlay: focus on open, body scroll lock,
 * and Escape-to-close with listener cleanup.
 *
 * Extracted verbatim from Modal's single useEffect (dev_plan/03_PKG_dev_panel.md
 * Step 1) so SidePanel can reuse it instead of the codebase growing a second,
 * subtly different copy. Returns the ref to attach to the dialog element.
 */
export function useOverlayBehavior(
  isOpen: boolean,
  onClose: () => void,
): React.RefObject<HTMLDivElement | null> {
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return

    // Focus the dialog on open
    dialogRef.current?.focus()

    // Lock scroll
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"

    // Handle Escape key
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose()
      }
    }

    document.addEventListener("keydown", handleEscape)

    return () => {
      document.removeEventListener("keydown", handleEscape)
      document.body.style.overflow = originalOverflow
    }
  }, [isOpen, onClose])

  return dialogRef
}
