import { Modal } from "@/components/ui/Modal"
import { Button } from "@/components/ui/Button"
import { RiAlertLine } from "@remixicon/react"

/**
 * Same shape as ConfirmDeleteModal (centered alert icon, title, description,
 * Cancel + destructive confirm), minus the isPending/error props that modal
 * needs for its API call — discarding is synchronous, nothing to await or
 * fail. Pair with useConfirmedClose rather than rendering directly.
 */
export function ConfirmDiscardModal({
  isOpen,
  onCancel,
  onDiscard,
}: {
  isOpen: boolean
  onCancel: () => void
  onDiscard: () => void
}) {
  if (!isOpen) return null

  return (
    <Modal isOpen onClose={onCancel} hideClose className="max-w-[512px]">
      <div className="flex flex-col items-center pt-6 text-center">
        <div className="flex h-[58px] w-[58px] items-center justify-center relative overflow-hidden mb-4">
          <RiAlertLine size={44} className="text-danger z-10" />
        </div>
        <div className="flex flex-col items-center text-center w-full space-y-2 mb-4">
          <h3 className="text-lg font-semibold text-fg leading-[28px]">Discard unsaved changes?</h3>
          <div className="text-sm font-normal leading-[20px] text-fg-muted">
            You have unsaved changes. Closing now will lose them.
          </div>
        </div>
        <div className="flex w-full items-center justify-end gap-2 mt-2">
          <Button type="button" variant="outline" size="md" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" variant="primary" size="md" onClick={onDiscard}>
            Discard changes
          </Button>
        </div>
      </div>
    </Modal>
  )
}
