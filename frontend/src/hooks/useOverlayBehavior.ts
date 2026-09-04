import { useEffect, useId, useRef } from "react"

/**
 * Ids of every currently-open overlay, in the order they opened. An overlay
 * nested inside an already-open one (e.g. a snapshot lightbox opened from
 * within the incident detail modal) pushes on top; Escape only acts on the
 * last entry, so one keypress closes the topmost overlay and nothing behind
 * it.
 */
const openOverlayStack: string[] = []

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
  const id = useId()

  // Latest onClose without making it an effect dependency — an overlay's
  // onClose is commonly a fresh closure every render, and re-running the
  // effect on every such change would reorder openOverlayStack even though
  // nothing about open-ness actually changed.
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  })

  useEffect(() => {
    if (!isOpen) return

    // Focus the dialog on open
    dialogRef.current?.focus()

    // Lock scroll
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"

    openOverlayStack.push(id)

    // Handle Escape key — only the topmost open overlay responds.
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      if (openOverlayStack[openOverlayStack.length - 1] !== id) return
      onCloseRef.current()
    }

    document.addEventListener("keydown", handleEscape)

    return () => {
      document.removeEventListener("keydown", handleEscape)
      document.body.style.overflow = originalOverflow
      const idx = openOverlayStack.indexOf(id)
      if (idx !== -1) openOverlayStack.splice(idx, 1)
    }
  }, [isOpen, id])

  return dialogRef
}
