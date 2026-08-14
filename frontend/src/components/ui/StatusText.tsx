import type { ReactNode } from "react"

import { cn } from "@/utils/cn"
import type { AlertStatus } from "@/api/alerts"
import type { CameraAiStatus, CameraConnectionStatus } from "@/api/cameras"
import {
  getAlertStatusTone,
  getCameraAiTone,
  getCameraConnectionTone,
  TONE_CLASS,
  type StatusTone,
} from "@/components/ui/statusTone"

/**
 * Renders a domain status in its semantic colour. The status-to-tone mapping
 * lives in `statusTone.ts`; this file is the rendering half.
 */
export function StatusText({
  tone,
  description,
  className,
  children,
}: {
  tone: StatusTone
  /**
   * An optional second line under the status, in muted caption type.
   *
   * A status word alone often can't carry the whole meaning: three cameras
   * can all read `Paused` for three unrelated reasons, one of which needs an
   * operator and two of which do not. The distinction lives in the data, so
   * the primitive has somewhere to put it rather than each screen inventing
   * its own layout for the same problem.
   */
  description?: ReactNode
  className?: string
  children: ReactNode
}) {
  const status = (
    <span className={cn("text-secondary font-medium", TONE_CLASS[tone], className)}>
      {children}
    </span>
  )

  if (!description) return status

  return (
    <span className="flex flex-col gap-0.5">
      {status}
      <span className="text-caption text-fg-muted">{description}</span>
    </span>
  )
}

/** Convenience wrappers so a call site names the domain, not the tone. */
export function AlertStatusText({ status }: { status: AlertStatus }) {
  return <StatusText tone={getAlertStatusTone(status)}>{status}</StatusText>
}

export function CameraConnectionText({ status }: { status: CameraConnectionStatus }) {
  return <StatusText tone={getCameraConnectionTone(status)}>{status}</StatusText>
}

export function CameraAiText({
  status,
  description,
}: {
  status: CameraAiStatus
  description?: ReactNode
}) {
  return (
    <StatusText tone={getCameraAiTone(status)} description={description}>
      {status}
    </StatusText>
  )
}
