import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { RiAlertLine } from "@remixicon/react"

import { expectedRestoreConfirmation, requestRestore } from "@/api/maintenance"
import { getApiErrorMessage } from "@/api/client"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Modal } from "@/components/ui/Modal"
import { PasswordInput } from "@/components/ui/PasswordInput"

interface RestoreConfirmModalProps {
  backupId: string
  onClose: () => void
  onSuccess: () => void
}

/**
 * Two confirmation layers, neither optional, neither pre-filled: the
 * admin's current password, plus an exact `RESTORE <backup_id>` string
 * typed by hand (`RestoreRequestIn.expected_confirmation`,
 * schemas/maintenance.py). Local state only, and this component fully
 * unmounts on close (Maintenance.tsx renders it conditionally rather than
 * toggling a hidden prop) — nothing here is remembered between opens.
 *
 * A 202 from this route is a *request*, not a completed restore — it
 * writes a flag file for an external orchestrator to act on later with
 * services stopped. The copy below says so; "Request Restore" rather than
 * "Restore" is deliberate.
 */
export function RestoreConfirmModal({ backupId, onClose, onSuccess }: RestoreConfirmModalProps) {
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")

  const expected = expectedRestoreConfirmation(backupId)
  const canSubmit = password.length > 0 && confirmation === expected

  const mutation = useMutation({
    mutationFn: requestRestore,
    onSuccess,
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSubmit) return
    mutation.mutate({ backup_id: backupId, current_password: password, confirmation })
  }

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Request Restore"
      subtitle={`Backup ${backupId}`}
      icon={
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-danger-border bg-danger-subtle">
          <RiAlertLine size={20} className="text-danger" />
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-6">
        <div className="space-y-4">
          <p className="text-xs leading-relaxed text-fg-muted">
            This does not restore anything by itself — it writes a request that an external operator
            carries out later, offline, with services stopped. The system will go offline shortly
            after you submit this.
          </p>

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
            {getApiErrorMessage(mutation.error, "Unable to request the restore.")}
          </p>
        ) : null}

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-stroke-strong bg-transparent px-4 py-2 text-xs font-medium text-fg-body transition-colors hover:text-fg"
          >
            Cancel
          </button>
          <Button
            type="submit"
            variant="destructive"
            size="sm"
            disabled={!canSubmit}
            isLoading={mutation.isPending}
            loadingLabel="Requesting…"
          >
            Request Restore
          </Button>
        </div>
      </form>
    </Modal>
  )
}
