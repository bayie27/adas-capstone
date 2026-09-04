import { useState } from "react"

/**
 * Wraps a modal's `onClose` so unsaved input isn't lost to a stray backdrop
 * click, the X button, or Escape — all three already funnel through one
 * `onClose` call (Modal.tsx / useOverlayBehavior.ts), so intercepting it
 * here covers every close path without the caller handling each separately.
 *
 * Gates on `isDirty` (real unsaved content), not on whether a field is
 * currently showing a validation error — an error can't exist without some
 * content already behind it, except a required-field error from submitting
 * a still-empty form, which has nothing worth protecting.
 */
export function useConfirmedClose(isDirty: boolean, onClose: () => void) {
  const [isConfirmOpen, setIsConfirmOpen] = useState(false)

  function requestClose() {
    if (isDirty) {
      setIsConfirmOpen(true)
      return
    }
    onClose()
  }

  function confirmDiscard() {
    setIsConfirmOpen(false)
    onClose()
  }

  function cancelDiscard() {
    setIsConfirmOpen(false)
  }

  return { requestClose, isConfirmOpen, confirmDiscard, cancelDiscard }
}
