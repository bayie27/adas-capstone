import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  RiArrowDownSLine,
  RiArrowRightSLine,
  RiHardDrive2Line,
  RiRefreshLine,
} from "@remixicon/react"

import { getBackups, triggerBackup, type BackupRead } from "@/api/maintenance"
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
import { formatFullDateTime } from "@/utils/datetime"
import { formatFileSize } from "@/utils/format"

const BACKUPS_QUERY_KEY = ["system-backups"] as const
const TABLE_COLUMN_COUNT = 5

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
}: {
  backup: BackupRead
  expanded: boolean
  onToggle: () => void
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
          <TableCell colSpan={TABLE_COLUMN_COUNT} className="bg-canvas">
            {/*
              `valid` alone hides which gate passed — a backup whose checks
              disagree with its own valid flag (a partial failure the
              summary can't distinguish from a clean pass) is exactly the
              case a restore candidate needs to be able to tell apart.
            */}
            <div className="flex flex-wrap gap-2 py-2">
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
                    {name}: {ok ? "OK" : "Failed"}
                  </Badge>
                ))
              )}
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

  const backupsQuery = useQuery({
    queryKey: BACKUPS_QUERY_KEY,
    queryFn: getBackups,
  })

  /**
   * POST /api/system/backups returns 202 immediately — the actual write
   * runs in a background task. There is nothing to poll for completion (no
   * job id), so this refetches the list once after a short delay to have a
   * decent chance of showing the new row, and the operator can always hit
   * Refresh themselves; a 409 means one is already running.
   */
  const triggerMutation = useMutation({
    mutationFn: triggerBackup,
    onSuccess: () => {
      setNotice({ tone: "success", message: "Backup started." })
      window.setTimeout(() => queryClient.invalidateQueries({ queryKey: BACKUPS_QUERY_KEY }), 4000)
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
        <div className="flex items-center gap-2.5">
          <RiHardDrive2Line size={18} className="text-fg-muted" />
          <div>
            <h1 className="mb-0.5 text-xl font-semibold text-fg">Maintenance</h1>
            <p className="text-xs text-fg-muted">
              Database backups and the restore request flow — never a filesystem path
            </p>
          </div>
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
            Trigger Backup
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
                />
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </div>
  )
}
