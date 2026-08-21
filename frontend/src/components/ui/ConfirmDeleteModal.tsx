import { Modal } from "@/components/ui/Modal"
import { getApiErrorMessage } from "@/api/client"
import { RiAlertLine } from "@remixicon/react"
import { Button } from "@/components/ui/Button"

interface ConfirmDeleteModalProps {
  isOpen: boolean
  title: string
  description: React.ReactNode
  isPending: boolean
  error: unknown
  confirmText?: string
  /**
   * Overrides what `error` would render. For a failure the caller can explain
   * better than the envelope can — a 400 that means "something else has to
   * happen first" rather than "that didn't work".
   */
  errorMessage?: string | null
  onClose: () => void
  onConfirm: () => void
}

export function ConfirmDeleteModal({
  isOpen,
  title,
  description,
  isPending,
  error,
  errorMessage,
  confirmText = "Continue",
  onClose,
  onConfirm,
}: ConfirmDeleteModalProps) {
  if (!isOpen) return null

  return (
    <Modal isOpen onClose={onClose} hideClose className="max-w-[512px]">
      <div className="flex flex-col items-center pt-6 text-center">
        <RiAlertLine size={48} className="mb-4 text-danger" />
        <h3 className="mb-2 text-lg font-semibold text-fg">{title}</h3>
        <div className="mb-6 px-4 text-sm font-normal leading-relaxed text-fg-muted">
          {description}
        </div>

        {error || errorMessage ? (
          <p className="mb-4 text-sm text-danger">
            {errorMessage ?? getApiErrorMessage(error, "Action failed.")}
          </p>
        ) : null}

        <div className="flex w-full justify-end gap-2 mt-4">
          <Button type="button" variant="outline" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            isLoading={isPending}
            loadingLabel="Deleting..."
            onClick={onConfirm}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
