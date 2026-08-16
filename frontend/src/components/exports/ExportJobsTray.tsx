import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  RiAlertLine,
  RiCloseLine,
  RiDownloadLine,
  RiRefreshLine,
  RiTimerLine,
} from "@remixicon/react"

import { downloadExportJob, getExportJob, type ExportJobRead } from "@/api/exports"
import { Badge, type BadgeTone } from "@/components/ui/Badge"
import { Button, focusRing } from "@/components/ui/Button"
import { SidePanel } from "@/components/ui/SidePanel"
import { useExportJobsStore, type TrackedExportJob } from "@/store/useExportJobsStore"
import { useNow } from "@/hooks/useNow"
import { formatRelativeDateTime } from "@/utils/datetime"
import { failureMessage } from "@/utils/exportJobs"
import { cn } from "@/utils/cn"
import { useState } from "react"

const POLL_INTERVAL_MS = 3000
// A safety valve, not a backend timeout — EXPORT_JOB_WORKERS is 1, so a
// queue backed up behind a slow job is a real, if unusual, situation. After
// this long still queued/processing, stop polling automatically and hand the
// operator a manual "Check now" rather than spinning a timer forever.
const POLL_CEILING_MS = 5 * 60 * 1000

const REPORT_TYPE_LABEL: Record<string, string> = {
  incidents: "Incident log",
  dashboard: "Dashboard",
  performance: "AI performance",
  audit: "Audit log",
  retraining: "Retraining package",
}

const STATUS_TONE: Record<string, BadgeTone> = {
  queued: "neutral",
  processing: "warning",
  completed: "success",
  failed: "danger",
  expired: "neutral",
}

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  expired: "Expired",
}

function JobRow({
  tracked,
  now,
  onRemove,
}: {
  tracked: TrackedExportJob
  now: number
  onRemove: () => void
}) {
  const queryClient = useQueryClient()
  const createdAtMs = new Date(tracked.createdAt).getTime()
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const jobQuery = useQuery({
    queryKey: ["export-job", tracked.jobId],
    queryFn: () => getExportJob(tracked.jobId),
    refetchInterval: (query) => {
      const data = query.state.data as ExportJobRead | undefined
      if (!data) return POLL_INTERVAL_MS
      if (data.status === "completed" || data.status === "failed" || data.status === "expired") {
        return false
      }
      return Date.now() - createdAtMs > POLL_CEILING_MS ? false : POLL_INTERVAL_MS
    },
  })

  const job = jobQuery.data
  const status = job?.status
  const timedOut =
    Boolean(status) &&
    (status === "queued" || status === "processing") &&
    now - createdAtMs > POLL_CEILING_MS

  async function handleDownload() {
    if (!job) return
    setDownloadError(null)
    try {
      await downloadExportJob(job)
    } catch {
      setDownloadError("Download failed. The file may have expired — try again.")
    }
  }

  return (
    <div className="border-b border-stroke py-3 last:border-b-0">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium text-fg">
            {REPORT_TYPE_LABEL[tracked.reportType] ?? tracked.reportType}
            <span className="ml-1 text-fg-muted">&middot; {tracked.format.toUpperCase()}</span>
          </p>
          <p className="text-caption text-fg-muted">{formatRelativeDateTime(tracked.createdAt)}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {status ? (
            <Badge tone={STATUS_TONE[status] ?? "neutral"} variant="subtle">
              {STATUS_LABEL[status] ?? status}
            </Badge>
          ) : null}
          <button
            type="button"
            onClick={onRemove}
            aria-label="Remove from this list"
            className={cn(
              "rounded-sm text-fg-muted transition-colors duration-150 hover:text-fg",
              focusRing,
            )}
          >
            <RiCloseLine size={14} />
          </button>
        </div>
      </div>

      {timedOut ? (
        <div className="mt-2 flex items-center justify-between gap-2 rounded-md border border-stroke bg-surface-2 px-2.5 py-1.5">
          <span className="flex items-center gap-1.5 text-caption text-fg-muted">
            <RiTimerLine size={13} />
            Taking longer than expected.
          </span>
          <Button
            size="sm"
            variant="outline"
            className="h-6 px-2 text-[10px]"
            onClick={() => queryClient.refetchQueries({ queryKey: ["export-job", tracked.jobId] })}
          >
            <RiRefreshLine size={12} />
            Check now
          </Button>
        </div>
      ) : null}

      {status === "completed" ? (
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="text-caption text-fg-muted">
            {job?.progress_total !== null && job?.progress_total !== undefined
              ? `${new Intl.NumberFormat("en-US").format(job.progress_total)} rows`
              : null}
          </span>
          <Button size="sm" onClick={handleDownload}>
            <RiDownloadLine size={13} />
            Download
          </Button>
        </div>
      ) : null}

      {status === "failed" ? (
        <p className="mt-2 flex items-start gap-1.5 text-caption text-danger">
          <RiAlertLine size={13} className="mt-0.5 shrink-0" />
          {failureMessage(job?.failure_category ?? null)}
        </p>
      ) : null}

      {status === "expired" ? (
        <p className="mt-2 text-caption text-fg-muted">
          This export's file has been removed after its 72-hour retention window. Re-run the export
          to get a new file.
        </p>
      ) : null}

      {downloadError ? <p className="mt-2 text-caption text-danger">{downloadError}</p> : null}
    </div>
  )
}

/**
 * A global, persistent tray for async export jobs — mounted once in App.tsx
 * (like MaintenanceNotice/DevPanelTrigger) so a job started on one page keeps
 * polling while the operator navigates elsewhere, and survives a reload.
 *
 * There is no `GET /api/exports/jobs` list route, so "jobs from an earlier
 * session" means jobs *this browser* created (`useExportJobsStore`,
 * localStorage-backed) — not every job the account has ever run from any
 * device. Documented here rather than implied by the UI copy.
 */
export function ExportJobsTray() {
  const jobs = useExportJobsStore((state) => state.jobs)
  const untrack = useExportJobsStore((state) => state.untrack)
  const [isOpen, setIsOpen] = useState(false)
  // Only ticks while the panel is open — the timeout check only needs to be
  // fresh when a row is actually visible, not while the tray sits collapsed.
  const now = useNow(isOpen, 5000)

  if (jobs.length === 0) return null

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label="Export jobs"
        className={cn(
          "fixed bottom-4 left-4 z-[8000] flex h-10 w-10 items-center justify-center rounded-full",
          "border border-stroke bg-surface-1 text-fg-muted shadow-overlay transition-colors duration-150",
          "hover:text-fg",
          focusRing,
        )}
      >
        <RiDownloadLine size={18} />
      </button>

      <SidePanel
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Export jobs"
        subtitle="Background exports started from this browser"
      >
        {jobs.map((tracked) => (
          <JobRow
            key={tracked.jobId}
            tracked={tracked}
            now={now}
            onRemove={() => untrack(tracked.jobId)}
          />
        ))}

        {/*
          G2 — GET /api/exports/jobs (a list route) doesn't exist, only
          single-job GET by id, so "history" here can only ever mean jobs
          this browser's own useExportJobsStore tracked. States that scope
          limit outright instead of leaving it implied by what's absent.
          The button is the seam: the day G2 ships, its onClick becomes a
          real fetch and disabled goes away -- no structural change to the
          tray itself.
        */}
        <div className="mt-4 space-y-2 border-t border-stroke pt-3">
          <p className="text-caption text-fg-muted">
            Showing exports started from this browser only.
          </p>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled
              className="flex-1"
              title="Not available yet -- no endpoint lists a user's export jobs across sessions (G2)"
            >
              Load history from other sessions
            </Button>
            <Badge tone="neutral" variant="subtle" uppercase={false} className="shrink-0">
              Unavailable
            </Badge>
          </div>
        </div>
      </SidePanel>
    </>
  )
}
