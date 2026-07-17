import { useEffect, useMemo, useState, type ReactNode } from "react"

import { API_BASE_URL } from "@/utils/env"
import { cn } from "@/utils/cn"

const BACKEND_HTTP_ORIGIN = API_BASE_URL.replace(/\/+$/, "").replace(/\/api$/, "")
const KNOWN_IMAGE_EXTENSION_PATTERN = /\.(jpg|jpeg|png|webp)$/i

interface SnapshotImageProps {
  snapshotPath: string | null | undefined
  alt: string
  className?: string
  fallbackClassName?: string
  fallbackContent?: ReactNode
  loading?: "eager" | "lazy"
}

function encodePathSegments(value: string) {
  return value
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/")
}

function hasKnownImageExtension(value: string) {
  return KNOWN_IMAGE_EXTENSION_PATTERN.test(value)
}

function expandImageCandidates(baseUrl: string) {
  if (hasKnownImageExtension(baseUrl)) {
    return [baseUrl]
  }

  return [baseUrl, `${baseUrl}.jpg`, `${baseUrl}.jpeg`, `${baseUrl}.png`]
}

function resolveSnapshotUrls(snapshotPath: string | null | undefined) {
  if (!snapshotPath) {
    return []
  }

  const normalized = String(snapshotPath).trim().replace(/\\/g, "/")

  if (!normalized) {
    return []
  }

  if (/^https?:\/\//i.test(normalized)) {
    return [normalized]
  }

  if (normalized.startsWith("/snapshots/")) {
    return expandImageCandidates(`${BACKEND_HTTP_ORIGIN}${encodeURI(normalized)}`)
  }

  if (normalized.startsWith("snapshots/")) {
    return expandImageCandidates(`${BACKEND_HTTP_ORIGIN}/${encodePathSegments(normalized)}`)
  }

  if (normalized.startsWith("/")) {
    return [`${BACKEND_HTTP_ORIGIN}${encodeURI(normalized)}`]
  }

  const fileName = normalized.split("/").pop()

  if (!fileName) {
    return []
  }

  return expandImageCandidates(`${BACKEND_HTTP_ORIGIN}/snapshots/${encodeURIComponent(fileName)}`)
}

export function SnapshotImage({
  snapshotPath,
  alt,
  className,
  fallbackClassName,
  fallbackContent,
  loading = "lazy",
}: SnapshotImageProps) {
  const snapshotUrls = useMemo(() => resolveSnapshotUrls(snapshotPath), [snapshotPath])
  const [candidateIndex, setCandidateIndex] = useState(0)

  useEffect(() => {
    setCandidateIndex(0)
  }, [snapshotUrls])

  const currentSnapshotUrl = snapshotUrls[candidateIndex] ?? null

  if (!currentSnapshotUrl) {
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
      src={currentSnapshotUrl}
      alt={alt}
      loading={loading}
      className={className}
      onError={() => {
        // Try the next candidate before showing the fallback state.
        setCandidateIndex((currentIndex) => currentIndex + 1)
      }}
    />
  )
}
