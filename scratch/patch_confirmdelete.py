with open("frontend/src/components/ui/ConfirmDeleteModal.tsx") as f:
    content = f.read()

# Update props interface
content = content.replace("description: string", "description: React.ReactNode")
content = content.replace("error: unknown", "error: unknown\n  confirmText?: string")

new_return = """
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
      <div className="flex flex-col items-center pt-2 text-center">
        <RiAlertLine size={48} className="mb-4 text-danger" />
        <h3 className="mb-2 text-lg font-semibold text-fg">{title}</h3>
        <div className="mb-6 px-4 text-sm font-normal leading-relaxed text-fg-muted">{description}</div>

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
"""

start_idx = content.find("export function ConfirmDeleteModal")
content = content[:start_idx] + new_return

with open("frontend/src/components/ui/ConfirmDeleteModal.tsx", "w") as f:
    f.write(content)
