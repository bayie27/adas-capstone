import { useState, type ReactNode } from "react"

import { API_BASE_URL } from "@/utils/env"
import { cn } from "@/utils/cn"

const BACKEND_HTTP_ORIGIN = API_BASE_URL.replace(/\/+$/, "").replace(/\/api$/, "")

interface SnapshotImageProps {
  snapshotUrl: string | null | undefined
  alt: string
  className?: string
  fallbackClassName?: string
  fallbackContent?: ReactNode
  loading?: "eager" | "lazy"
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
}: SnapshotImageProps) {
  const src = resolveSnapshotSrc(snapshotUrl)
  const [failedSrc, setFailedSrc] = useState<string | null>(null)

  if (!src || src === failedSrc) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-md border border-dashed border-[#7F1D1D] bg-[#111111] text-xs text-[#FCA5A5]",
          fallbackClassName,
        )}
      >
        {fallbackContent ?? "Snapshot unavailable"}
      </div>
    )
  }

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
