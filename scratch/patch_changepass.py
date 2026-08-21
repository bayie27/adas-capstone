with open("frontend/src/pages/users/ChangePasswordModal.tsx") as f:
    content = f.read()

# Rename the component and prop types
content = content.replace("ResetPasswordModal", "ChangePasswordModal")
content = content.replace("ResetPasswordFormState", "ChangePasswordFormState")
content = content.replace("ResetPasswordModalProps", "ChangePasswordModalProps")

new_return = """
  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Change User Password"
      subtitle="Update a user's password"
      className="bg-surface-2"
    >
      <form onSubmit={handleSubmit} className="flex flex-col">
        <hr className="border-t border-stroke mb-6 -mx-6" />

        <div className="flex flex-col gap-6">
          <p className="text-base font-normal text-fg">
            Changing {getUserFullName(user)}'s account's password...
          </p>

          <div className="flex flex-col gap-4">
            <PasswordInput
              label="New Password"
              value={form.new_password}
              disabled={mutation.isPending}
              onChange={(value) => updateField("new_password", value)}
              className="text-base text-fg-muted"
              labelClassName="text-base font-medium text-fg"
            />
            <PasswordInput
              label="Confirm New Password"
              value={form.confirm_password}
              disabled={mutation.isPending}
              onChange={(value) => updateField("confirm_password", value)}
              className="text-base text-fg-muted"
              labelClassName="text-base font-medium text-fg"
            />
          </div>

          <div className="text-base font-normal text-fg-muted">
            Must be at least 8 characters long and contain at least 1 number.
          </div>

          <div className="mt-2">
            <p className="rounded-md border border-warning-border bg-warning-subtle px-4 py-3 text-sm font-medium text-warning">
              Resetting this password will sign {getUserFullName(user)} out of every active session immediately.
            </p>
          </div>
        </div>

        {errorMessage ? <p className="mt-4 text-sm text-danger">{errorMessage}</p> : null}

        <hr className="border-t border-stroke my-6 -mx-6" />

        <div className="flex items-center justify-between">
          <div className="text-sm font-medium text-fg-muted">
            Last Changes: {formatShortDateTime(user.password_changed_at ?? null)}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={mutation.isPending} loadingLabel="Saving…">
              Save Changes
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
"""

start_idx = content.find("  return (")
content = content[:start_idx] + new_return

with open("frontend/src/pages/users/ChangePasswordModal.tsx", "w") as f:
    f.write(content)
