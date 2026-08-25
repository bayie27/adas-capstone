import { useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  RiArrowDownSLine,
  RiArrowRightSLine,
  RiInformationLine,
  RiRefreshLine,
} from "@remixicon/react"

import { getBackups, getLatestRestore, triggerBackup, type BackupRead } from "@/api/maintenance"
import { getApiError, getApiErrorMessage } from "@/api/client"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { NoticeBanner, type NoticeState } from "@/components/ui/NoticeBanner"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeaderCell,
  TableRow,
  TableStateRow,
} from "@/components/ui/Table"
import { RestoreConfirmModal } from "@/pages/maintenance/RestoreConfirmModal"
import { formatFullDateTime } from "@/utils/datetime"
import { formatFileSize } from "@/utils/format"

const BACKUPS_QUERY_KEY = ["system-backups"] as const
const LATEST_RESTORE_QUERY_KEY = ["latest-restore"] as const
const TABLE_COLUMN_COUNT = 5

// Mirrors settings.BACKUP_DAILY_RETENTION / BACKUP_MANUAL_RETENTION
// (backend/app/core/config.py) -- fixed retention counts, not returned by
// GET /api/system/backups, so declared here rather than left unstated.
const BACKUP_DAILY_RETENTION = 30
const BACKUP_MANUAL_RETENTION = 10

const RESTORE_STATUS_LABEL: Record<string, string> = {
  requested: "Requested",
  in_progress: "In progress",
  db_restored: "Database restored",
  completed: "Completed",
  failed: "Failed",
  rolled_back: "Rolled back",
}

/**
 * Display-layer mapping from raw backup.checks keys (set by the backend) to
 * plain-language labels for operations staff. Covers all current check names;
 * unknown future keys fall back to formatCheckLabel below so they never
 * silently disappear from the UI.
 */
const CHECK_LABELS: Record<string, string> = {
  checksum: "File Integrity",
  quick_check: "Database Structure",
  foreign_key_check: "Data Links",
}

/**
 * Returns the friendly label for a check key, or a lightly formatted version
 * of the raw key (title-case, underscores → spaces) for any unmapped key
 * added later on the backend.
 */
function formatCheckLabel(key: string): string {
  if (CHECK_LABELS[key]) return CHECK_LABELS[key]
  return key
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

function ValidityBadge({ valid }: { valid: boolean }) {
  return (
    <Badge variant="subtle" tone={valid ? "success" : "danger"}>
      {valid ? "Valid" : "Invalid"}
    </Badge>
  )
}

function BackupRow({
  backup,
  expanded,
  onToggle,
  onRequestRestore,
}: {
  backup: BackupRead
  expanded: boolean
  onToggle: () => void
  onRequestRestore: (backupId: string) => void
}) {
  const checkEntries = Object.entries(backup.checks)

  return (
    <>
      <TableRow className="cursor-pointer" onClick={onToggle}>
        <TableCell className="font-mono text-caption text-fg-muted">{backup.backup_id}</TableCell>
        <TableCell className="text-fg-muted">{formatFullDateTime(backup.created_at)}</TableCell>
        <TableCell className="text-fg-muted">{backup.origin}</TableCell>
        <TableCell className="text-fg-muted">{formatFileSize(backup.file_size)}</TableCell>
        <TableCell className="text-right">
          <ValidityBadge valid={backup.valid} />
          {expanded ? (
            <RiArrowDownSLine size={14} className="ml-2 inline text-fg-muted" />
          ) : (
            <RiArrowRightSLine size={14} className="ml-2 inline text-fg-muted" />
          )}
        </TableCell>
      </TableRow>
      {expanded ? (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={TABLE_COLUMN_COUNT} className="bg-canvas py-6">
            {/*
              `valid` alone hides which gate passed — a backup whose checks
              disagree with its own valid flag (a partial failure the
              summary can't distinguish from a clean pass) is exactly the
              case a restore candidate needs to be able to tell apart.
            */}
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-caption font-medium text-fg-muted mr-1">
                  Validation Checks:
                </span>
                {checkEntries.length === 0 ? (
                  <span className="text-caption text-fg-muted">No check detail recorded.</span>
                ) : (
                  checkEntries.map(([name, ok]) => (
                    <Badge
                      key={name}
                      variant="outline"
                      tone={ok ? "success" : "danger"}
                      uppercase={false}
                    >
                      {formatCheckLabel(name)}: {ok ? "Passed" : "Failed"}
                    </Badge>
                  ))
                )}
              </div>
              {/*
                Restore lives one interaction deeper than the backup list
                itself (expand, then click) and only appears for a manifest-
                valid backup — get_valid_backup rejects anything else
                server-side anyway (maintenance/restore.py:145-152), so an
                invalid backup gets no misleading affordance to click.
                Spatial and interaction distance from "Trigger Backup" above
                is deliberate: the two actions should never be one careless
                click apart.
              */}
              {backup.valid ? (
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-stroke pt-2.5">
                  <span className="text-caption text-fg-muted">
                    Restore database state and rollback to this backup point.
                  </span>
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    onClick={(event) => {
                      event.stopPropagation()
                      onRequestRestore(backup.backup_id)
                    }}
                  >
                    Request Restore
                  </Button>
                </div>
              ) : null}
            </div>
          </TableCell>
        </TableRow>
      ) : null}
    </>
  )
}

/**
 * D-1 (settled): third ADMINISTRATION nav row, same guard as Users/Audit
 * Log — the parent /admin route already requires Admin (Phase 5); nothing
 * new added here. D-4/D-7 (design authority, no Figma frame): the backup
 * list follows the same toolbar-and-table shape as Audit Log, with the
 * expandable-row pattern (Audit Log's `detail`) reused for `checks` rather
 * than a second modal.
 */
export default function Maintenance() {
  const queryClient = useQueryClient()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [notice, setNotice] = useState<NoticeState | null>(null)
  const [restoreTargetId, setRestoreTargetId] = useState<string | null>(null)

  /**
   * Snapshot of backup IDs that existed before a Create Backup was triggered.
   * Used after the 4-second delayed refetch to detect whether a new row
   * appeared — if so, the background task finished within the window.
   */
  const preBackupIdsRef = useRef<Set<string>>(new Set())

  const backupsQuery = useQuery({
    queryKey: BACKUPS_QUERY_KEY,
    queryFn: getBackups,
  })

  const latestRestoreQuery = useQuery({
    queryKey: LATEST_RESTORE_QUERY_KEY,
    queryFn: getLatestRestore,
  })

  /**
   * POST /api/system/backups returns 202 immediately — the actual write
   * runs in a background task. There is nothing to poll for completion (no
   * job id). We snapshot the current backup IDs at trigger time, then after a
   * short delay fetch the list again and compare: if a new row appeared the
   * task finished within that window and we update the banner accordingly;
   * if not, we prompt the operator to refresh manually. A 409 means one is
   * already running.
   */
  const triggerMutation = useMutation({
    mutationFn: triggerBackup,
    onSuccess: () => {
      // Capture what already exists before the new backup lands
      preBackupIdsRef.current = new Set(
        (
          queryClient.getQueryData<Awaited<ReturnType<typeof getBackups>>>(BACKUPS_QUERY_KEY)
            ?.items ?? []
        ).map((b) => b.backup_id),
      )
      setNotice({ tone: "warning", message: "Backup started. Please wait…" })
      window.setTimeout(async () => {
        const result = await queryClient.fetchQuery({
          queryKey: BACKUPS_QUERY_KEY,
          queryFn: getBackups,
          staleTime: 0,
        })
        const hasNew = result.items.some((b) => !preBackupIdsRef.current.has(b.backup_id))
        setNotice(
          hasNew
            ? {
                tone: "success",
                message: "Backup complete. The new backup is now available in the list.",
              }
            : {
                tone: "warning",
                message:
                  "Backup started. It is still running in the background — click Refresh to check when it's ready.",
              },
        )
        window.setTimeout(() => setNotice(null), 5000)
      }, 4000)
    },
    onError: (error) => {
      const isBusy = getApiError(error)?.code === "CONFLICT_BUSY"
      setNotice({
        tone: "error",
        message: isBusy
          ? "A backup or restore is already running."
          : getApiErrorMessage(error, "Unable to start a backup."),
      })
    },
  })

  const backups = backupsQuery.data?.items ?? []

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6 flex items-center justify-between gap-3">
        <div>
          <h1 className="mb-0.5 text-xl font-semibold text-fg">Maintenance</h1>
          <p className="text-xs text-fg-muted">
            Manage system database backups and safe point-in-time restoration.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => backupsQuery.refetch()}
            disabled={backupsQuery.isFetching}
          >
            <RiRefreshLine size={13} />
            Refresh
          </Button>
          <Button
            size="sm"
            isLoading={triggerMutation.isPending}
            loadingLabel="Starting…"
            onClick={() => {
              setNotice(null)
              triggerMutation.mutate()
            }}
          >
            Create Backup
          </Button>
        </div>
      </div>

      {notice ? <NoticeBanner notice={notice} /> : null}

      {backupsQuery.isError ? (
        <QueryErrorBanner
          error={backupsQuery.error}
          fallback="Unable to load the backup list."
          onRetry={() => backupsQuery.refetch()}
        />
      ) : null}

      <p className="mb-3 flex items-center gap-1.5 text-sm italic text-fg-muted">
        <RiInformationLine size={14} className="shrink-0" />
        The system safely retains up to {BACKUP_DAILY_RETENTION} daily and {BACKUP_MANUAL_RETENTION}{" "}
        manual backups. Older records are deleted automatically.
      </p>

      <TableContainer>
        <Table>
          <TableHead>
            <TableHeaderCell>Backup ID</TableHeaderCell>
            <TableHeaderCell>Created</TableHeaderCell>
            <TableHeaderCell>Origin</TableHeaderCell>
            <TableHeaderCell>Size</TableHeaderCell>
            <TableHeaderCell className="text-right">Validity</TableHeaderCell>
          </TableHead>
          <TableBody>
            {backupsQuery.isLoading ? (
              <TableStateRow colSpan={TABLE_COLUMN_COUNT}>Loading backups...</TableStateRow>
            ) : backups.length === 0 ? (
              <TableStateRow colSpan={TABLE_COLUMN_COUNT}>No backups yet.</TableStateRow>
            ) : (
              backups.map((backup) => (
                <BackupRow
                  key={backup.backup_id}
                  backup={backup}
                  expanded={expandedId === backup.backup_id}
                  onToggle={() =>
                    setExpandedId((current) =>
                      current === backup.backup_id ? null : backup.backup_id,
                    )
                  }
                  onRequestRestore={setRestoreTargetId}
                />
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/*
        POST /api/system/restores only ever writes a request flag file — the
        offline restore itself runs later, with services stopped, so this
        browser has no signal for when (or whether) it finishes. Rather than
        auto-reload on a timer that can't know when the system is back, this
        renders whatever GET /restores/latest last reported and leaves
        reloading to the operator once they've actually run the offline
        step. MAINTENANCE_NOTICE (Phase 12's banner, already wired app-wide
        in App.tsx) is what tells every connected dashboard the socket is
        about to drop — this section is the durable record, not the
        real-time warning.
      */}
      {latestRestoreQuery.data ? (
        <div className="mt-6 rounded-xl border border-stroke bg-surface-1 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-fg">Restore Status</h2>
              <p className="mt-1 text-caption text-fg-muted">
                Backup {latestRestoreQuery.data.backup_id} &middot; requested{" "}
                {formatFullDateTime(latestRestoreQuery.data.requested_at)}
                {latestRestoreQuery.data.requested_by
                  ? ` by ${latestRestoreQuery.data.requested_by}`
                  : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge
                variant="subtle"
                tone={
                  latestRestoreQuery.data.status === "completed"
                    ? "success"
                    : latestRestoreQuery.data.status === "failed"
                      ? "danger"
                      : "neutral"
                }
              >
                {RESTORE_STATUS_LABEL[latestRestoreQuery.data.status] ??
                  latestRestoreQuery.data.status}
              </Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={() => latestRestoreQuery.refetch()}
                disabled={latestRestoreQuery.isFetching}
              >
                <RiRefreshLine size={13} />
                Refresh
              </Button>
              {/*
                Always offered, not just once a terminal status arrives —
                the operator's own browser can never observe the offline
                steps progress in real time (the backend is down while they
                run), so "check back and reload the whole app" is the
                honest action at every stage, not just the end.
              */}
              <Button size="sm" onClick={() => window.location.reload()}>
                Reload app
              </Button>
            </div>
          </div>

          {latestRestoreQuery.data.status === "requested" ? (
            <p className="mt-3 text-caption text-fg-muted">
              Waiting on a person — nothing happens automatically from here. Stop services and run{" "}
              <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[11px]">
                python -m app.maintenance restore {latestRestoreQuery.data.backup_id}
              </code>{" "}
              from the command line to complete it.
            </p>
          ) : null}

          {latestRestoreQuery.data.error ? (
            <p className="mt-3 text-caption text-danger">{latestRestoreQuery.data.error}</p>
          ) : null}
        </div>
      ) : null}

      {restoreTargetId ? (
        <RestoreConfirmModal
          backupId={restoreTargetId}
          onClose={() => setRestoreTargetId(null)}
          onSuccess={() => {
            setNotice({
              tone: "success",
              message: `Restore requested for backup ${restoreTargetId}. Nothing happens automatically — stop services and run the offline restore procedure to complete it.`,
            })
            setRestoreTargetId(null)
            queryClient.invalidateQueries({ queryKey: LATEST_RESTORE_QUERY_KEY })
          }}
        />
      ) : null}
    </div>
  )
}
