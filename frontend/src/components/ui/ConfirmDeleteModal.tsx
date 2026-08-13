import { Modal } from "@/components/ui/Modal"
import { getApiErrorMessage } from "@/utils/api"
import { RiAlertLine } from "@remixicon/react"

interface ConfirmDeleteModalProps {
  isOpen: boolean
  title: string
  description: string
  isPending: boolean
  error: unknown
  onClose: () => void
  onConfirm: () => void
}

export function ConfirmDeleteModal({
  isOpen,
  title,
  description,
  isPending,
  error,
  onClose,
  onConfirm,
}: ConfirmDeleteModalProps) {
  if (!isOpen) return null

  return (
    <Modal isOpen onClose={onClose} hideClose>
      <div className="flex flex-col items-center pt-6 text-center">
        <RiAlertLine size={36} className="mb-4 text-danger" />
        <h3 className="mb-2 text-[15px] font-bold text-white">{title}</h3>
        <p className="mb-6 px-4 text-[11px] leading-relaxed text-fg-muted">{description}</p>
        {error ? (
          <p className="mb-4 text-xs text-danger">{getApiErrorMessage(error, "Action failed.")}</p>
        ) : null}
        <div className="flex w-full items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-stroke-strong bg-transparent px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-surface-1"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={onConfirm}
            className="rounded-md bg-white px-4 py-2 text-xs font-semibold text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? "Deleting..." : "Continue"}
          </button>
        </div>
      </div>
    </Modal>
  )
}
