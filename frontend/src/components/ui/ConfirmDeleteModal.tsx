import { Modal } from "@/components/ui/Modal"
import { getApiErrorMessage } from "@/api/client"
import { RiAlertLine } from "@remixicon/react"
import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

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
        <h3 className="mb-2 text-[15px] font-bold text-fg">{title}</h3>
        <p className="mb-6 px-4 text-[11px] leading-relaxed text-fg-muted">{description}</p>
        {error ? (
          <p className="mb-4 text-xs text-danger">{getApiErrorMessage(error, "Action failed.")}</p>
        ) : null}
        <div className="flex w-full items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className={cn(
              "rounded-md border border-stroke-strong bg-transparent px-4 py-2 text-xs font-semibold text-fg transition-colors duration-150 hover:bg-surface-2",
              focusRing,
            )}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={onConfirm}
            className={cn(
              "rounded-md bg-primary px-4 py-2 text-xs font-semibold text-fg-on-primary transition-colors duration-150 hover:bg-primary-hover",
              "disabled:cursor-not-allowed disabled:opacity-60",
              focusRing,
            )}
          >
            {isPending ? "Deleting..." : "Continue"}
          </button>
        </div>
      </div>
    </Modal>
  )
}
