import type { ReactNode } from "react"

import { Badge } from "@/components/ui/Badge"
import { SidePanel } from "@/components/ui/SidePanel"
import type { CameraRecord } from "@/api/cameras"

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5 text-xs">
      <span className="font-medium tracking-[0.08em] text-fg-muted">{label}</span>
      <span className="text-right font-medium text-fg-body">{value}</span>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="border-b border-stroke py-4 first:pt-0 last:border-b-0 last:pb-0">
      <h4 className="mb-2 text-[10px] font-bold uppercase tracking-[0.08em] text-fg-muted">
        {title}
      </h4>
      {children}
    </div>
  )
}

/**
 * A labelled gap, not a placeholder — every "Unavailable" here is a real
 * absence in `CameraRead` (Q14), not a stand-in for a value the backend just
 * hasn't sent yet this render.
 */
function UnavailableNote({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-stroke bg-surface-2 px-3 py-2">
      <Badge tone="neutral" variant="subtle" uppercase={false} className="shrink-0">
        Unavailable
      </Badge>
      <p className="text-caption text-fg-muted">{children}</p>
    </div>
  )
}

/**
 * The camera detail panel — a `SidePanel`, per D-8(b): Cameras is a
 * reference surface an operator reads while comparing against the table,
 * not an interrupting decision like the Detections modal.
 *
 * `camera` is the row the table already fetched; this panel makes no
 * request of its own.
 */
export function CameraDetailPanel({
  camera,
  isOpen,
  onClose,
}: {
  camera: CameraRecord | null
  isOpen: boolean
  onClose: () => void
}) {
  if (!camera) return null

  return (
    <SidePanel
      isOpen={isOpen}
      onClose={onClose}
      title={camera.camera_name}
      subtitle={`Channel ${camera.channel_id}`}
    >
      <Section title="Identity">
        <DetailRow label="Camera name" value={camera.camera_name} />
        <DetailRow label="Channel" value={camera.channel_id} />
        <UnavailableNote>
          The RTSP stream URL is built by the backend from this channel and sent to the AI engine on
          every heartbeat, but never returned to the client (Q14). A wrong channel number produces a
          camera that looks configured and never connects, with no way to check the URL the system
          will actually dial.
        </UnavailableNote>
      </Section>
    </SidePanel>
  )
}
