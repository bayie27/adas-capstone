import { useState, type ReactNode } from "react"
import { RiZoomInLine } from "@remixicon/react"

import { API_BASE_URL } from "@/utils/env"
import { cn } from "@/utils/cn"
import { SnapshotZoomModal } from "@/components/ui/SnapshotZoomModal"

const BACKEND_HTTP_ORIGIN = API_BASE_URL.replace(/\/+$/, "").replace(/\/api$/, "")

interface SnapshotImageProps {
  snapshotUrl: string | null | undefined
  alt: string
  className?: string
  fallbackClassName?: string
  fallbackContent?: ReactNode
  loading?: "eager" | "lazy"
  /**
   * Opt-in click-to-zoom lightbox (RiZoomInLine badge over the image). Off
   * by default so surfaces like the ongoing-incidents tray thumbnail, which
   * already has its own hover-flyout preview, don't also become clickable.
   */
  zoomable?: boolean
}

// 01_CONTRACTS.md §5.9/§9.3 — `snapshot_url` is always an authorized API
// path like `/api/alerts/42/snapshot`, resolved against the backend origin.
// It is session-cookie authenticated; a same-site `<img src>` sends that
// cookie automatically, so no fetch wrapper is needed.
function resolveSnapshotSrc(snapshotUrl: string | null | undefined) {
  if (!snapshotUrl) {
    return null
  }

  return `${BACKEND_HTTP_ORIGIN}${snapshotUrl}`
}

export function SnapshotImage({
  snapshotUrl,
  alt,
  className,
  fallbackClassName,
  fallbackContent,
  loading = "lazy",
  zoomable = false,
}: SnapshotImageProps) {
  const src = resolveSnapshotSrc(snapshotUrl)
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const [isZoomOpen, setIsZoomOpen] = useState(false)

  // A modal can swap to a different alert's snapshot without unmounting
  // (e.g. paging through GlobalAlerts' queue) — an operator zoomed into one
  // accident must never still see themselves "zoomed in" once the image
  // underneath has silently changed to a different accident. Adjusted
  // during render (not an effect) per the React-recommended pattern for
  // resetting state on a prop change: https://react.dev/learn/you-might-not-need-an-effect
  const [prevSnapshotUrl, setPrevSnapshotUrl] = useState(snapshotUrl)
  if (snapshotUrl !== prevSnapshotUrl) {
    setPrevSnapshotUrl(snapshotUrl)
    setIsZoomOpen(false)
  }

  if (!src || src === failedSrc) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-md border border-dashed border-danger-border bg-surface-1 text-xs text-danger",
          fallbackClassName,
        )}
      >
        {fallbackContent ?? "Snapshot unavailable"}
      </div>
    )
  }

  if (!zoomable) {
    return (
      <img
        src={src}
        alt={alt}
        loading={loading}
        className={className}
        onError={() => setFailedSrc(src)}
      />
    )
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setIsZoomOpen(true)}
        aria-label={`Zoom in on ${alt}`}
        className="group relative block h-full w-full cursor-zoom-in"
      >
        <img
          src={src}
          alt={alt}
          loading={loading}
          className={className}
          onError={() => setFailedSrc(src)}
        />
        <span className="absolute bottom-2 right-2 flex h-8 w-8 items-center justify-center rounded-full bg-black/70 text-white opacity-80 transition-opacity duration-150 group-hover:opacity-100">
          <RiZoomInLine size={18} />
        </span>
      </button>
      <SnapshotZoomModal
        isOpen={isZoomOpen}
        onClose={() => setIsZoomOpen(false)}
        src={src}
        alt={alt}
      />
    </>
  )
}
