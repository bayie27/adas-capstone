import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  RiAlertLine,
  RiCloseLine,
  RiDownloadLine,
  RiRefreshLine,
  RiTimerLine,
} from "@remixicon/react"

import { downloadExportJob, getExportJob, listExportJobs, type ExportJobRead } from "@/api/exports"
import { Badge, type BadgeTone } from "@/components/ui/Badge"
import { Button, focusRing } from "@/components/ui/Button"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { SidePanel } from "@/components/ui/SidePanel"
import { useExportJobsStore, type TrackedExportJob } from "@/store/useExportJobsStore"
import { useNow } from "@/hooks/useNow"
import { formatRelativeDateTime } from "@/utils/datetime"
import { failureMessage } from "@/utils/exportJobs"
import { cn } from "@/utils/cn"
import { useState } from "react"
import { toast } from "@/store/useToastStore"

const POLL_INTERVAL_MS = 3000
const HISTORY_PAGE_SIZE = 20
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
      toast.success("Export downloaded successfully.")
    } catch {
      toast.error("Download failed. The file may have expired.")
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
 * A history row already carries its full `ExportJobRead` from the list
 * fetch — unlike `JobRow`, it does not poll `GET /api/exports/jobs/{id}`
 * itself. Most history rows are already terminal (completed/failed/
 * expired) by the time an operator asks to see them; a row still
 * queued/processing on another device simply reflects whatever the list
 * returned until the tray is reopened, which is an acceptable staleness
 * for a "what did I run earlier" view, not a live status board.
 */
function HistoryJobRow({ job }: { job: ExportJobRead }) {
  const [downloadError, setDownloadError] = useState<string | null>(null)

  async function handleDownload() {
    setDownloadError(null)
    try {
      await downloadExportJob(job)
      toast.success("Export downloaded successfully.")
    } catch {
      toast.error("Download failed. The file may have expired.")
      setDownloadError("Download failed. The file may have expired — try again.")
    }
  }

  return (
    <div className="border-b border-stroke py-3 last:border-b-0">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium text-fg">
            {REPORT_TYPE_LABEL[job.report_type] ?? job.report_type}
            <span className="ml-1 text-fg-muted">&middot; {job.format.toUpperCase()}</span>
          </p>
          <p className="text-caption text-fg-muted">{formatRelativeDateTime(job.created_at)}</p>
        </div>
        <Badge tone={STATUS_TONE[job.status] ?? "neutral"} variant="subtle">
          {STATUS_LABEL[job.status] ?? job.status}
        </Badge>
      </div>

      {job.status === "completed" ? (
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="text-caption text-fg-muted">
            {job.progress_total !== null
              ? `${new Intl.NumberFormat("en-US").format(job.progress_total)} rows`
              : null}
          </span>
          <Button size="sm" onClick={handleDownload}>
            <RiDownloadLine size={13} />
            Download
          </Button>
        </div>
      ) : null}

      {job.status === "failed" ? (
        <p className="mt-2 flex items-start gap-1.5 text-caption text-danger">
          <RiAlertLine size={13} className="mt-0.5 shrink-0" />
          {failureMessage(job.failure_category)}
        </p>
      ) : null}

      {job.status === "expired" ? (
        <p className="mt-2 text-caption text-fg-muted">
          This export's file has been removed after its 72-hour retention window.
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
 * `GET /api/exports/jobs` (P21 Step 4) now lists the caller's own jobs
 * account-wide, so "history" is no longer limited to what this browser's
 * `useExportJobsStore` happened to track. That local store still drives the
 * "This session" list (it has live polling and an untrack action neither
 * makes sense for another device's jobs), but it is no longer the only
 * source of history.
 */
export function ExportJobsTray() {
  const jobs = useExportJobsStore((state) => state.jobs)
  const untrack = useExportJobsStore((state) => state.untrack)
  const [isOpen, setIsOpen] = useState(false)
  // Only ticks while the panel is open — the timeout check only needs to be
  // fresh when a row is actually visible, not while the tray sits collapsed.
  const now = useNow(isOpen, 5000)

  const [historyRequested, setHistoryRequested] = useState(false)
  const [historyOffset, setHistoryOffset] = useState(0)
  const [historyItems, setHistoryItems] = useState<ExportJobRead[]>([])
  const [appendedOffset, setAppendedOffset] = useState<number | null>(null)

  const historyQuery = useQuery({
    queryKey: ["export-jobs-history", historyOffset],
    queryFn: () => listExportJobs({ limit: HISTORY_PAGE_SIZE, offset: historyOffset }),
    enabled: historyRequested,
  })

  // Append each page's items exactly once, during render rather than an
  // effect -- the same "sync derived state while rendering" idiom
  // Users.tsx/Detections.tsx already use for query-derived pagination
  // totals. Converges immediately: appendedOffset catches up to
  // historyOffset on the next render and stops firing until it changes again.
  if (historyQuery.data && appendedOffset !== historyOffset) {
    setHistoryItems((current) => [...current, ...historyQuery.data!.items])
    setAppendedOffset(historyOffset)
  }

  // A job started this session already appears in the tracked list above --
  // don't show it a second time once the account-wide history also returns it.
  const trackedIds = new Set(jobs.map((tracked) => tracked.jobId))
  const dedupedHistory = historyItems.filter((item) => !trackedIds.has(item.job_id))
  const totalFiltered = historyQuery.data?.total_filtered ?? historyItems.length
  const hasMore = historyRequested && historyItems.length < totalFiltered

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label={`Export jobs${jobs.length > 0 ? ` (${jobs.length})` : ""}`}
        title="Export jobs"
        className={cn(
          "fixed top-5 right-5 z-[8000] flex h-11 w-11 items-center justify-center rounded-lg",
          "border border-stroke bg-surface-1 text-fg-muted shadow-overlay transition-all duration-150",
          "hover:border-stroke-strong hover:bg-surface-2 hover:text-fg active:scale-95",
          focusRing,
        )}
      >
        <RiDownloadLine size={20} />
        {jobs.length > 0 ? (
          <span
            className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold leading-none text-white shadow-sm ring-2 ring-surface-1"
            aria-hidden="true"
          >
            {jobs.length}
          </span>
        ) : null}
      </button>

      <SidePanel
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Export jobs"
        subtitle="Background exports, this browser and earlier sessions"
      >
        {jobs.length > 0 ? (
          <>
            {historyRequested ? (
              <h4 className="mb-1 text-[10px] font-bold uppercase tracking-[0.08em] text-fg-muted">
                This session
              </h4>
            ) : null}
            {jobs.map((tracked) => (
              <JobRow
                key={tracked.jobId}
                tracked={tracked}
                now={now}
                onRemove={() => untrack(tracked.jobId)}
              />
            ))}
          </>
        ) : !historyRequested ? (
          <p className="py-6 text-center text-caption text-fg-muted">
            No exports tracked in this browser yet.
          </p>
        ) : null}

        <div
          className={cn(
            jobs.length > 0 || historyRequested ? "mt-4 border-t border-stroke pt-3" : "",
          )}
        >
          {!historyRequested ? (
            <Button
              size="sm"
              variant="outline"
              className="w-full"
              onClick={() => setHistoryRequested(true)}
            >
              Load history from other sessions
            </Button>
          ) : (
            <>
              <h4 className="mb-1 text-[10px] font-bold uppercase tracking-[0.08em] text-fg-muted">
                Earlier sessions
              </h4>

              {historyQuery.isError ? (
                <QueryErrorBanner
                  error={historyQuery.error}
                  fallback="Unable to load export history."
                  onRetry={() => historyQuery.refetch()}
                />
              ) : null}

              {historyQuery.isLoading ? (
                <p className="py-4 text-center text-caption text-fg-muted">Loading…</p>
              ) : dedupedHistory.length === 0 && !historyQuery.isError ? (
                <p className="py-4 text-center text-caption text-fg-muted">No earlier exports.</p>
              ) : (
                dedupedHistory.map((job) => <HistoryJobRow key={job.job_id} job={job} />)
              )}

              {hasMore ? (
                <div className="mt-3 flex justify-center">
                  <Button
                    size="sm"
                    variant="outline"
                    isLoading={historyQuery.isFetching}
                    loadingLabel="Loading…"
                    onClick={() => setHistoryOffset((current) => current + HISTORY_PAGE_SIZE)}
                  >
                    Load more
                  </Button>
                </div>
              ) : null}
            </>
          )}
        </div>
      </SidePanel>
    </>
  )
}
