import { Modal } from "@/components/ui/Modal"
import { getApiErrorMessage } from "@/api/client"
import { RiAlertLine } from "@remixicon/react"
import { Button } from "@/components/ui/Button"
import type { ReactNode } from "react"

interface ConfirmDeleteModalProps {
  isOpen: boolean
  title: string
  description: ReactNode
  isPending: boolean
  error: unknown
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
  onClose,
  onConfirm,
}: ConfirmDeleteModalProps) {
  if (!isOpen) return null

  return (
    <Modal isOpen onClose={onClose} hideClose className="max-w-[512px]">
      <div className="flex flex-col items-center pt-6 text-center">
        <div className="flex h-[58px] w-[58px] items-center justify-center relative overflow-hidden mb-4">
          <RiAlertLine size={44} className="text-danger z-10" />
        </div>
        <div className="flex flex-col items-center text-center w-full space-y-2 mb-4">
          <h3 className="text-lg font-semibold text-fg leading-[28px]">{title}</h3>
          <div className="text-sm font-normal leading-[20px] text-fg-muted">{description}</div>
        </div>
        {error ? (
          <p className="mb-4 text-sm text-danger text-center">
            {errorMessage ?? getApiErrorMessage(error, "Action failed.")}
          </p>
        ) : null}
        <div className="flex w-full items-center justify-end gap-2 mt-2">
          <Button type="button" variant="outline" size="md" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="md"
            isLoading={isPending}
            loadingLabel="Deleting..."
            onClick={onConfirm}
          >
            Continue
          </Button>
        </div>
      </div>
    </Modal>
  )
}
