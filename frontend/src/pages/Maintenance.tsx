import { useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  RiArrowDownSLine,
  RiArrowRightSLine,
  RiInformationLine,
  RiRefreshLine,
} from "@remixicon/react"

import {
  getBackups,
  getLatestRestore,
  getMaintenanceStatus,
  triggerBackup,
  type BackupRead,
  type RestoreStatus,
} from "@/api/maintenance"
import { getApiError, getApiErrorMessage } from "@/api/client"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
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
import { toast } from "@/store/useToastStore"

const BACKUPS_QUERY_KEY = ["system-backups"] as const
const LATEST_RESTORE_QUERY_KEY = ["latest-restore"] as const
const MAINTENANCE_STATUS_QUERY_KEY = ["maintenance-status"] as const
const TABLE_COLUMN_COUNT = 5

const BACKUP_DAILY_RETENTION = 30
const BACKUP_MANUAL_RETENTION = 10

const ACTIVE_RESTORE_STATUSES = new Set<RestoreStatus>(["requested", "in_progress", "db_restored"])
const TERMINAL_RESTORE_STATUSES = new Set<RestoreStatus>(["completed", "failed", "rolled_back"])

const RESTORE_STATUS_LABEL: Record<RestoreStatus, string> = {
  requested: "Requested",
  in_progress: "In progress",
  db_restored: "Database restored",
  completed: "Completed",
  failed: "Failed",
  rolled_back: "Rolled back",
}

const CHECK_LABELS: Record<string, string> = {
  checksum: "File Integrity",
  quick_check: "Database Structure",
  foreign_key_check: "Data Links",
  file_size: "File Size",
  artifact_name: "Artifact Name",
}

function formatCheckLabel(key: string): string {
  if (CHECK_LABELS[key]) return CHECK_LABELS[key]
  return key
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

function formatBackupOrigin(origin: string) {
  if (origin === "manual") return "Manual backup"
  if (origin === "scheduled") return "Scheduled backup"
  if (origin === "pre-restore") return "Pre-restore backup"
  return origin
}

function restoreBadgeTone(status: RestoreStatus) {
  if (status === "completed") return "success" as const
  if (status === "failed") return "danger" as const
  if (status === "rolled_back" || status === "db_restored") return "warning" as const
  return "neutral" as const
}

function coordinatorUnavailableReason(
  state: "unavailable" | "idle" | "executing" | "error" | undefined,
) {
  if (state === "executing") return "A restore is already in progress."
  return "Automatic restore is unavailable because the maintenance service is not running."
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
  restoreAvailable,
  restoreUnavailableReason,
}: {
  backup: BackupRead
  expanded: boolean
  onToggle: () => void
  onRequestRestore: (backup: BackupRead) => void
  restoreAvailable: boolean
  restoreUnavailableReason: string
}) {
  const checkEntries = Object.entries(backup.checks)

  return (
    <>
      <TableRow className="cursor-pointer" onClick={onToggle} aria-expanded={expanded}>
        <TableCell className="text-fg-muted">
          <div>{formatFullDateTime(backup.created_at)}</div>
        </TableCell>
        <TableCell className="text-fg-muted">{formatBackupOrigin(backup.origin)}</TableCell>
        <TableCell className="text-fg-muted">{formatFileSize(backup.file_size)}</TableCell>
        <TableCell>
          <ValidityBadge valid={backup.valid} />
        </TableCell>
        <TableCell className="text-right">
          {expanded ? (
            <RiArrowDownSLine size={14} className="inline text-fg-muted" />
          ) : (
            <RiArrowRightSLine size={14} className="inline text-fg-muted" />
          )}
        </TableCell>
      </TableRow>
      {expanded ? (
        <TableRow className="hover:bg-transparent" onClick={(event) => event.stopPropagation()}>
          <TableCell colSpan={TABLE_COLUMN_COUNT} className="bg-canvas py-6">
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="mr-1 text-caption font-medium text-fg-muted">
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

              {backup.valid ? (
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-stroke pt-2.5">
                  <span className="text-caption text-fg-muted">
                    Choose this date, origin, and size as the restore point.
                  </span>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    {!restoreAvailable ? (
                      <span className="text-right text-caption text-fg-muted">
                        {restoreUnavailableReason}
                      </span>
                    ) : null}
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      disabled={!restoreAvailable}
                      onClick={() => onRequestRestore(backup)}
                    >
                      Restore this backup…
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          </TableCell>
        </TableRow>
      ) : null}
    </>
  )
}

export default function Maintenance() {
  const queryClient = useQueryClient()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [restoreTarget, setRestoreTarget] = useState<BackupRead | null>(null)
  const preBackupIdsRef = useRef<Set<string>>(new Set())
  const sawActiveRestoreRef = useRef(false)

  const backupsQuery = useQuery({
    queryKey: BACKUPS_QUERY_KEY,
    queryFn: getBackups,
  })

  const statusQuery = useQuery({
    queryKey: MAINTENANCE_STATUS_QUERY_KEY,
    queryFn: getMaintenanceStatus,
    refetchInterval: 2_000,
  })

  const latestRestoreQuery = useQuery({
    queryKey: LATEST_RESTORE_QUERY_KEY,
    queryFn: getLatestRestore,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && ACTIVE_RESTORE_STATUSES.has(status) ? 2_000 : false
    },
  })

  useEffect(() => {
    const state = latestRestoreQuery.data
    if (!state) return
    if (ACTIVE_RESTORE_STATUSES.has(state.status)) {
      sawActiveRestoreRef.current = true
      return
    }
    if (TERMINAL_RESTORE_STATUSES.has(state.status) && sawActiveRestoreRef.current) {
      sawActiveRestoreRef.current = false
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: BACKUPS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: LATEST_RESTORE_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: MAINTENANCE_STATUS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ["my-profile"] }),
        queryClient.invalidateQueries({ queryKey: ["cameras"] }),
        queryClient.invalidateQueries({ queryKey: ["alerts"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] }),
      ])
    }
  }, [latestRestoreQuery.data, queryClient])

  const triggerMutation = useMutation({
    mutationFn: triggerBackup,
    onSuccess: () => {
      preBackupIdsRef.current = new Set(
        (
          queryClient.getQueryData<Awaited<ReturnType<typeof getBackups>>>(BACKUPS_QUERY_KEY)
            ?.items ?? []
        ).map((backup) => backup.backup_id),
      )
      toast.info("Database backup started in the background.")
      window.setTimeout(async () => {
        const result = await queryClient.fetchQuery({
          queryKey: BACKUPS_QUERY_KEY,
          queryFn: getBackups,
          staleTime: 0,
        })
        const hasNew = result.items.some((backup) => !preBackupIdsRef.current.has(backup.backup_id))
        toast[hasNew ? "success" : "info"](
          hasNew
            ? "Database backup created successfully."
            : "Backup is still processing in the background.",
        )
      }, 4_000)
    },
    onError: (error) => {
      const isBusy = getApiError(error)?.code === "CONFLICT_BUSY"
      toast.error(
        isBusy
          ? "A backup or restore is already running."
          : getApiErrorMessage(error, "Unable to start a backup."),
      )
    },
  })

  const backups = backupsQuery.data?.items ?? []
  const coordinator = statusQuery.data?.restore_coordinator
  const restoreAvailable = coordinator?.available === true
  const restoreUnavailableReason = coordinatorUnavailableReason(coordinator?.state)
  const latestRestore = latestRestoreQuery.data

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
            onClick={() => triggerMutation.mutate()}
          >
            Create Backup
          </Button>
        </div>
      </div>

      {backupsQuery.isError ? (
        <QueryErrorBanner
          error={backupsQuery.error}
          fallback="Unable to load the backup list."
          onRetry={() => backupsQuery.refetch()}
        />
      ) : null}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-stroke bg-surface-1 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-fg">Automatic restore service</h2>
          <p className="mt-1 text-caption text-fg-muted">
            {restoreAvailable
              ? "Ready to accept a selected validated backup."
              : restoreUnavailableReason}
          </p>
        </div>
        <Badge variant="subtle" tone={restoreAvailable ? "success" : "neutral"}>
          {restoreAvailable ? "Ready" : coordinator?.state === "executing" ? "Busy" : "Unavailable"}
        </Badge>
      </div>

      <p className="mb-3 flex items-center gap-1.5 text-sm italic text-fg-muted">
        <RiInformationLine size={14} className="shrink-0" />
        The system safely retains up to {BACKUP_DAILY_RETENTION} daily and {BACKUP_MANUAL_RETENTION}{" "}
        manual backups. Older records are deleted automatically.
      </p>

      <TableContainer>
        <Table>
          <TableHead>
            <TableHeaderCell>Date and time</TableHeaderCell>
            <TableHeaderCell>Origin</TableHeaderCell>
            <TableHeaderCell>Size</TableHeaderCell>
            <TableHeaderCell>Validity</TableHeaderCell>
            <TableHeaderCell className="text-right">Details</TableHeaderCell>
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
                  onRequestRestore={setRestoreTarget}
                  restoreAvailable={restoreAvailable}
                  restoreUnavailableReason={restoreUnavailableReason}
                />
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {latestRestore ? (
        <div className="mt-6 rounded-lg border border-stroke bg-surface-1 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-fg">Restore Status</h2>
              <p className="mt-1 text-caption text-fg-muted">
                Requested {formatFullDateTime(latestRestore.requested_at)}
                {latestRestore.requested_by ? ` by ${latestRestore.requested_by}` : ""}
              </p>
            </div>
            <Badge variant="subtle" tone={restoreBadgeTone(latestRestore.status)}>
              {RESTORE_STATUS_LABEL[latestRestore.status]}
            </Badge>
          </div>

          {latestRestore.status === "requested" ? (
            <p className="mt-3 text-caption text-fg-muted">
              The selected restore point is queued. The system will restart automatically when the
              maintenance service claims it.
            </p>
          ) : null}
          {latestRestore.status === "in_progress" ? (
            <p className="mt-3 text-caption text-fg-muted">
              The database restore is in progress. This page will update when the system is
              available again.
            </p>
          ) : null}
          {latestRestore.status === "db_restored" ? (
            <p className="mt-3 text-caption text-fg-muted">
              The database was replaced and the system is checking service readiness.
            </p>
          ) : null}
          {latestRestore.status === "rolled_back" ? (
            <p className="mt-3 text-caption text-warning">
              The selected restore point did not pass the readiness check. The original database was
              recovered safely.
            </p>
          ) : null}
          {latestRestore.error ? (
            <p className="mt-3 text-caption text-danger">{latestRestore.error}</p>
          ) : null}
          {latestRestore.steps.length > 0 ? (
            <p className="mt-3 text-caption text-fg-muted">
              Latest step: {latestRestore.steps[latestRestore.steps.length - 1].name}
            </p>
          ) : null}
        </div>
      ) : null}

      {restoreTarget ? (
        <RestoreConfirmModal
          backup={restoreTarget}
          onClose={() => setRestoreTarget(null)}
          onSuccess={(response) => {
            toast.success(response.detail)
            sawActiveRestoreRef.current = true
            setRestoreTarget(null)
            void queryClient.invalidateQueries({ queryKey: LATEST_RESTORE_QUERY_KEY })
            void queryClient.invalidateQueries({ queryKey: MAINTENANCE_STATUS_QUERY_KEY })
          }}
        />
      ) : null}
    </div>
  )
}
