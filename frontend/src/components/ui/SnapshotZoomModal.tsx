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
 */
export function SnapshotZoomModal({ isOpen, onClose, src, alt }: SnapshotZoomModalProps) {
  const dialogRef = useOverlayBehavior(isOpen, onClose)

  if (!isOpen) return null

  return (
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
        className="relative flex max-h-full max-w-full flex-col items-center gap-4 outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <TransformWrapper minScale={1} maxScale={6} centerOnInit doubleClick={{ mode: "toggle" }}>
          {({ zoomIn, zoomOut, resetTransform }) => (
            <>
              <TransformComponent
                wrapperClass="max-h-[80vh] max-w-[90vw]"
                contentClass="max-h-[80vh] max-w-[90vw]"
              >
                <img
                  src={src}
                  alt={alt}
                  draggable={false}
                  className="max-h-[80vh] max-w-[90vw] select-none object-contain"
                />
              </TransformComponent>

              <div className="flex items-center gap-1 rounded-full border border-white/20 bg-black/80 p-1 shadow-2xl backdrop-blur-md">
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
    </div>
  )
}
