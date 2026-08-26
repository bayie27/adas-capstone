import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { RiAlertLine, RiFileCopyLine } from "@remixicon/react"

import {
  expectedRestoreConfirmation,
  requestRestore,
  type BackupRead,
  type RestoreTriggerResponse,
} from "@/api/maintenance"
import { getApiErrorMessage } from "@/api/client"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Modal } from "@/components/ui/Modal"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { truncateId } from "@/utils/auditFormat"
import { formatFullDateTime } from "@/utils/datetime"
import { formatFileSize } from "@/utils/format"

interface RestoreConfirmModalProps {
  backup: BackupRead
  onClose: () => void
  onSuccess: (response: RestoreTriggerResponse) => void
}

function formatBackupOrigin(origin: string) {
  if (origin === "manual") return "Manual backup"
  if (origin === "scheduled") return "Scheduled backup"
  if (origin === "pre-restore") return "Pre-restore backup"
  return origin
}

/**
 * The selected BackupRead object is kept intact from the table through this
 * modal. The summary is repeated immediately before the two confirmation
 * fields so an administrator can catch a mistaken point-in-time choice.
 */
export function RestoreConfirmModal({ backup, onClose, onSuccess }: RestoreConfirmModalProps) {
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [copied, setCopied] = useState(false)
  const expected = expectedRestoreConfirmation()
  const canSubmit = password.length > 0 && confirmation === expected

  async function handleCopyBackupId() {
    try {
      await navigator.clipboard.writeText(backup.backup_id)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard access is optional; the restore flow never depends on it.
    }
  }

  const mutation = useMutation({
    mutationFn: requestRestore,
    onSuccess,
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSubmit) return
    mutation.mutate({
      backup_id: backup.backup_id,
      current_password: password,
      confirmation,
    })
  }

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Restore database"
      subtitle="Review the selected restore point before continuing."
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-danger-border bg-danger-subtle">
          <RiAlertLine size={20} className="text-danger" />
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-6">
        <div className="rounded-lg border border-stroke bg-surface-2 p-4">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
            Selected backup
          </h2>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-xs">
            <dt className="text-fg-muted">Created</dt>
            <dd className="text-right text-fg">{formatFullDateTime(backup.created_at)}</dd>
            <dt className="text-fg-muted">Origin</dt>
            <dd className="text-right text-fg">{formatBackupOrigin(backup.origin)}</dd>
            <dt className="text-fg-muted">Size</dt>
            <dd className="text-right text-fg">{formatFileSize(backup.file_size)}</dd>
            <dt className="text-fg-muted">Validation</dt>
            <dd className="text-right">
              <Badge variant="subtle" tone={backup.valid ? "success" : "danger"}>
                {backup.valid ? "Valid" : "Invalid"}
              </Badge>
            </dd>
            <dt className="text-fg-muted">Reference (optional)</dt>
            <dd className="flex items-center justify-end gap-1 text-right text-fg">
              <span className="font-mono" title={backup.backup_id}>
                {truncateId(backup.backup_id)}
              </span>
              <button
                type="button"
                aria-label="Copy full backup ID"
                title={copied ? "Copied!" : "Copy full backup ID"}
                onClick={handleCopyBackupId}
                className="rounded p-0.5 text-fg-muted transition-colors hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-stroke-strong"
              >
                <RiFileCopyLine size={12} />
              </button>
            </dd>
          </dl>
        </div>

        <div className="space-y-2 rounded-lg border border-danger-border bg-danger-subtle p-4 text-xs leading-relaxed text-fg">
          <p>This replaces the current database with the selected historical restore point.</p>
          <p>
            Users will be signed out, and monitoring may be briefly unavailable while the system
            restarts.
          </p>
          <p>The system will restart automatically after you accept.</p>
          <p>Restoration is available only for a validated backup point.</p>
        </div>

        <div className="space-y-4">
          <PasswordInput
            label="Current Password"
            value={password}
            autoComplete="current-password"
            onChange={setPassword}
          />

          <Input
            label={`Type "${expected}" to confirm`}
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            autoComplete="off"
            placeholder={expected}
          />
        </div>

        {mutation.isError ? (
          <p className="text-xs text-danger">
            {getApiErrorMessage(mutation.error, "Unable to start the database restore.")}
          </p>
        ) : null}

        <div className="flex items-center justify-end gap-3">
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="destructive"
            size="sm"
            disabled={!canSubmit}
            isLoading={mutation.isPending}
            loadingLabel="Starting restore…"
          >
            Restore database
          </Button>
        </div>
      </form>
    </Modal>
  )
}
