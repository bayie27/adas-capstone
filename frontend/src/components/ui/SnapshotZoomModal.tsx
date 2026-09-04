import { createPortal } from "react-dom"
import { RiAddLine, RiCloseLine, RiSubtractLine } from "@remixicon/react"
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch"

import { useOverlayBehavior } from "@/hooks/useOverlayBehavior"
import { focusRing } from "@/components/ui/Button"
import { cn } from "@/utils/cn"

interface SnapshotZoomModalProps {
  isOpen: boolean
  onClose: () => void
  src: string
  alt: string
}

const controlButton = cn(
  "flex h-10 w-10 items-center justify-center rounded-full text-white transition-colors duration-150 hover:bg-white/10",
  focusRing,
)

/**
 * Fullscreen zoom/pan lightbox for a single accident snapshot, opened from
 * within an already-open incident/alarm modal. z-[10050] outranks every
 * existing overlay layer (GlobalAlerts' z-9999 is the next highest), and
 * useOverlayBehavior's open-overlay stack makes sure Escape closes only this
 * lightbox, not the modal underneath it.
 *
 * Portals to document.body rather than rendering in place: IncidentDetailModal's
 * dialog card carries `animate-modal-enter`, whose `animation-fill-mode: both`
 * leaves a permanent (if identity) `transform` on the card even after the
 * animation ends. Per the CSS spec that makes the card a new containing block
 * for any `position: fixed` descendant, so this lightbox — nested deep inside
 * it — would resolve `fixed inset-0` against the card's own box instead of the
 * viewport, rendering small and boxed-in instead of fullscreen. GlobalAlerts
 * doesn't hit this (it passes `noEntrance`, skipping that class), which is why
 * the same lightbox looked correctly fullscreen from there.
 */
export function SnapshotZoomModal({ isOpen, onClose, src, alt }: SnapshotZoomModalProps) {
  const dialogRef = useOverlayBehavior(isOpen, onClose)

  if (!isOpen) return null

  return createPortal(
    <div className="fixed inset-0 z-[10050] flex items-center justify-center p-4 sm:p-8">
      <div className="absolute inset-0 bg-black/90 cursor-pointer" onClick={onClose} />

      <button
        type="button"
        onClick={onClose}
        aria-label="Close zoomed snapshot"
        className={cn(
          "absolute right-4 top-4 z-10 flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-black/80 text-white transition-colors duration-150 hover:bg-black/95 sm:right-6 sm:top-6",
          focusRing,
        )}
      >
        <RiCloseLine size={24} />
      </button>

      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={alt}
        tabIndex={-1}
        className="relative flex h-[80vh] w-[90vw] max-h-full max-w-full flex-col items-center gap-4 outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <TransformWrapper minScale={1} maxScale={6} centerOnInit doubleClick={{ mode: "toggle" }}>
          {({ zoomIn, zoomOut, resetTransform }) => (
            <>
              {/* wrapperClass fills the flex-allocated box (flex-1 min-h-0) —
                  that part alone isn't enough, though: react-zoom-pan-pinch's
                  own stylesheet sets width/height on the content div at the
                  same specificity as a Tailwind utility class, so h-full/
                  w-full there loses the cascade tie and content silently
                  falls back to the image's natural size. Inline styles beat
                  that regardless of source order, so content and the img are
                  sized that way instead — otherwise a wide/high-res photo
                  renders taller than the wrapper actually is, and the library
                  "centers" the overflow by panning, which crops both edges. */}
              <TransformComponent
                wrapperClass="w-full min-h-0 flex-1"
                contentStyle={{
                  width: "100%",
                  height: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <img
                  src={src}
                  alt={alt}
                  draggable={false}
                  className="select-none"
                  style={{ width: "100%", height: "100%", objectFit: "contain" }}
                />
              </TransformComponent>

              <div className="flex shrink-0 items-center gap-1 rounded-full border border-white/20 bg-black/80 p-1 shadow-2xl backdrop-blur-md">
                <button
                  type="button"
                  onClick={() => zoomOut()}
                  aria-label="Zoom out"
                  className={controlButton}
                >
                  <RiSubtractLine size={20} />
                </button>
                <button
                  type="button"
                  onClick={() => resetTransform()}
                  aria-label="Reset zoom"
                  className={cn(
                    "h-10 rounded-full px-3 text-xs font-medium uppercase tracking-wide text-white transition-colors duration-150 hover:bg-white/10",
                    focusRing,
                  )}
                >
                  Reset
                </button>
                <button
                  type="button"
                  onClick={() => zoomIn()}
                  aria-label="Zoom in"
                  className={controlButton}
                >
                  <RiAddLine size={20} />
                </button>
              </div>
            </>
          )}
        </TransformWrapper>
      </div>
    </div>,
    document.body,
  )
}
