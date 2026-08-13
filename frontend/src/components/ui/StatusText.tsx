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
  className,
  children,
}: {
  tone: StatusTone
  className?: string
  children: ReactNode
}) {
  return (
    <span className={cn("text-secondary font-medium", TONE_CLASS[tone], className)}>
      {children}
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

export function CameraAiText({ status }: { status: CameraAiStatus }) {
  return <StatusText tone={getCameraAiTone(status)}>{status}</StatusText>
}
