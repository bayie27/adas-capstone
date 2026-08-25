import { useState, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"

import { Badge } from "@/components/ui/Badge"
import { focusRing } from "@/components/ui/Button"
import { SidePanel } from "@/components/ui/SidePanel"
import { CameraAiText, CameraConnectionText } from "@/components/ui/StatusText"
import { getCameraDetail } from "@/api/cameras"
import type { CameraRecord } from "@/api/cameras"
import { describeCameraDesiredState, secondsUntil } from "@/utils/format"
import { formatFullDateTime, secondsSince } from "@/utils/datetime"
import { cn } from "@/utils/cn"
import { RiEyeLine, RiEyeOffLine, RiFileCopyLine } from "@remixicon/react"
import { toast } from "@/store/useToastStore"

// Mirrors backend/app/core/config.py's HEARTBEAT_STALE_SECONDS -- not
// returned on CameraDetail, so declared here rather than left unstated.
const HEARTBEAT_STALE_SECONDS = 10

// Mirrors ai_engine/config.py's FPS_BAND_MIN/FPS_BAND_MAX -- the band the
// capacity decision is made against, not returned by any endpoint.
const FPS_BAND_MIN = 10
const FPS_BAND_MAX = 15

function formatFps(value: number): string {
  return `${value.toFixed(1)} fps`
}

function formatLatencyMs(value: number): string {
  return `${value.toFixed(0)} ms`
}

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

/** The explanation moves here, below the field rows it used to replace. */
function Footnote({ children }: { children: ReactNode }) {
  return <p className="mt-2 text-caption text-fg-muted">{children}</p>
}

/** Telemetry hasn't arrived yet this render — a fetch in flight, not a
 * permanent gap. Distinct from `UnavailableRow`, which means "the backend
 * has nothing here," not "not yet." */
function LoadingRow({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-xs">
      <span className="font-medium tracking-[0.08em] text-fg-muted">{label}</span>
      <span className="text-fg-muted">Loading…</span>
    </div>
  )
}

/**
 * `rtsp_url_redacted` arrives already masked by the backend
 * (`rtsp://***:***@host:port/path`) — there is no real credential behind it
 * to reveal. Hidden by default anyway (a detail panel is exactly the kind
 * of thing left open during a screen-share), so "reveal" only toggles
 * whether the masked host:port structure is visible, never anything more.
 * Copy copies that same masked string, with a tooltip so it is never
 * mistaken for a working connection string.
 */
function RedactedRtspRow({ value }: { value: string }) {
  const [visible, setVisible] = useState(false)
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      toast.info("Masked stream URL copied to clipboard.")
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard access can be denied (permissions, insecure context) --
      // silently doing nothing is safer than throwing over a copy button.
    }
  }

  return (
    <div className="flex items-center justify-between gap-2 py-1.5 text-xs">
      <span className="font-medium tracking-[0.08em] text-fg-muted">Stream URL</span>
      <span className="flex min-w-0 items-center gap-1.5">
        <span
          className="truncate font-mono text-[11px] text-fg-body"
          title={visible ? value : undefined}
        >
          {visible ? value : "Hidden — masked, no live credentials"}
        </span>
        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          aria-label={visible ? "Hide stream URL" : "Show stream URL"}
          className={cn(
            "shrink-0 rounded-sm text-fg-muted transition-colors duration-150 hover:text-fg",
            focusRing,
          )}
        >
          {visible ? <RiEyeLine size={14} /> : <RiEyeOffLine size={14} />}
        </button>
        <button
          type="button"
          onClick={handleCopy}
          aria-label="Copy masked stream URL"
          title="Copies the masked form shown above -- not a working connection string"
          className={cn(
            "shrink-0 rounded-sm text-fg-muted transition-colors duration-150 hover:text-fg",
            focusRing,
          )}
        >
          <RiFileCopyLine size={14} />
        </button>
      </span>
      {copied ? <span className="shrink-0 text-caption text-success">Copied</span> : null}
    </div>
  )
}

/**
 * The camera detail panel — a `SidePanel`, per D-8(b): Cameras is a
 * reference surface an operator reads while comparing against the table,
 * not an interrupting decision like the Detections modal.
 *
 * `camera` is the row the table already fetched; the seven telemetry
 * fields below are fresher than that row could ever be, since P21 shipped
 * `GET /api/cameras/{camera_id}` specifically so this drawer could fetch
 * them on open rather than read whatever the table's list query happened
 * to have minutes ago.
 */
export function CameraDetailPanel({
  camera,
  isOpen,
  onClose,
  now,
}: {
  camera: CameraRecord | null
  isOpen: boolean
  onClose: () => void
  /** Cameras.tsx's own `useNow` tick, reused rather than a second interval. */
  now: number
}) {
  const detailQuery = useQuery({
    queryKey: ["camera", camera?.camera_id],
    queryFn: () => getCameraDetail(camera!.camera_id),
    enabled: isOpen && camera !== null,
  })

  if (!camera) return null

  const detail = detailQuery.data
  const isLoading = detailQuery.isLoading

  const heartbeatAgeSeconds = detail?.last_heartbeat_at
    ? secondsSince(detail.last_heartbeat_at, now)
    : null
  const isHeartbeatStale =
    heartbeatAgeSeconds !== null && heartbeatAgeSeconds > HEARTBEAT_STALE_SECONDS

  const isFpsInBand =
    detail?.measured_fps !== null &&
    detail?.measured_fps !== undefined &&
    detail.measured_fps >= FPS_BAND_MIN &&
    detail.measured_fps <= FPS_BAND_MAX

  const cooldownSeconds =
    camera.desired_state_reason === "cooldown" ? secondsUntil(camera.cooldown_until, now) : null

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
        {isLoading ? (
          <LoadingRow label="Stream URL" />
        ) : detail?.rtsp_url_redacted ? (
          <RedactedRtspRow value={detail.rtsp_url_redacted} />
        ) : (
          <div className="flex items-center justify-between py-1.5 text-xs">
            <span className="font-medium tracking-[0.08em] text-fg-muted">Stream URL</span>
            <Badge tone="neutral" variant="subtle" uppercase={false}>
              Admin only
            </Badge>
          </div>
        )}
      </Section>

      <Section title="State">
        <div className="flex items-center justify-between py-1.5">
          <span className="text-xs font-medium tracking-[0.08em] text-fg-muted">Connection</span>
          <CameraConnectionText status={camera.connection_status} />
        </div>
        <div className="flex items-center justify-between py-1.5">
          <span className="text-xs font-medium tracking-[0.08em] text-fg-muted">AI detection</span>
          <CameraAiText
            status={camera.ai_status}
            description={describeCameraDesiredState(camera, now)}
          />
        </div>
        <DetailRow label="Desired state" value={camera.desired_ai_state} />
        <DetailRow label="Desired state reason" value={camera.desired_state_reason ?? "-"} />
        <DetailRow
          label="Cooldown"
          value={
            camera.desired_state_reason !== "cooldown"
              ? "-"
              : cooldownSeconds === null
                ? "Cooldown active"
                : cooldownSeconds > 0
                  ? `${cooldownSeconds}s remaining`
                  : "Resuming"
          }
        />
      </Section>

      <Section title="Convergence">
        <DetailRow label="Desired config version" value={camera.config_version} />
        {isLoading ? (
          <LoadingRow label="Applied config version" />
        ) : (
          <DetailRow label="Applied config version" value={detail?.applied_config_version ?? "-"} />
        )}
        <Footnote>
          "Desired" is what the backend wants right now; "Applied" is the config version the
          engine's own heartbeat last confirmed it picked up. The two disagreeing for more than a
          heartbeat or two is the substantiation for "the UI told me it was off" that Phase 6's
          optimistic enable/disable toggle couldn't offer on its own.
        </Footnote>
      </Section>

      <Section title="Engine telemetry">
        {isLoading ? (
          <>
            <LoadingRow label="Last heartbeat" />
            <LoadingRow label="Measured FPS" />
            <LoadingRow label="Inference latency" />
            <LoadingRow label="Last error code" />
          </>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2 py-1.5 text-xs">
              <span className="font-medium tracking-[0.08em] text-fg-muted">Last heartbeat</span>
              <span className="flex items-center gap-1.5">
                <span className="font-medium text-fg-body">
                  {formatFullDateTime(detail?.last_heartbeat_at)}
                </span>
                {isHeartbeatStale ? (
                  <Badge tone="warning" variant="subtle" uppercase={false}>
                    Stale
                  </Badge>
                ) : null}
              </span>
            </div>
            <DetailRow
              label="Measured FPS"
              value={
                detail?.measured_fps === null || detail?.measured_fps === undefined ? (
                  "-"
                ) : (
                  <span className={isFpsInBand ? "text-success" : "text-warning"}>
                    {formatFps(detail.measured_fps)}
                  </span>
                )
              }
            />
            <DetailRow
              label="Inference latency"
              value={
                detail?.inference_latency_ms === null || detail?.inference_latency_ms === undefined
                  ? "-"
                  : formatLatencyMs(detail.inference_latency_ms)
              }
            />
            <div className="flex items-center justify-between py-1.5 text-xs">
              <span className="font-medium tracking-[0.08em] text-fg-muted">Last error code</span>
              {detail?.last_error_code ? (
                <Badge tone="danger" variant="subtle" uppercase={false}>
                  {detail.last_error_code}
                </Badge>
              ) : (
                <Badge tone="neutral" variant="subtle" uppercase={false}>
                  None
                </Badge>
              )}
            </div>
            {detail?.last_error_message ? (
              <p className="mt-1 text-caption text-fg-muted">{detail.last_error_message}</p>
            ) : null}
          </>
        )}
        <Footnote>
          Last heartbeat, measured FPS (against the {FPS_BAND_MIN}–{FPS_BAND_MAX} FPS band),
          inference latency, and the engine's own error code plus its message are what tells a
          broken camera (an error code, a recent heartbeat) apart from a dead engine (a stale
          heartbeat, no error code).
        </Footnote>
      </Section>
    </SidePanel>
  )
}
