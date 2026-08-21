with open("frontend/src/pages/Users.tsx") as f:
    content = f.read()

old_modal = """      <ConfirmDeleteModal
        isOpen={modal.kind === "delete"}
        title="Are you absolutely sure?"
        description={
          modal.kind === "delete"
            ? `This action will deactivate account "${getUserFullName(modal.user)}" and remove it from the active user list.`
            : ""
        }
        isPending={deleteUserMutation.isPending}
        error={deleteUserMutation.error}
        onClose={() => setModal({ kind: "closed" })}
        onConfirm={() => {
          if (modal.kind === "delete") {
            setNotice(null)
            deleteUserMutation.mutate(modal.user.user_id)
          }
        }}
      />"""

new_modal = """      <ConfirmDeleteModal
        isOpen={modal.kind === "delete"}
        title="Are you absolutely sure?"
        description={
          modal.kind === "delete" ? (
            <>
              This action will deactivate account <span className="italic">"{getUserFullName(modal.user)}"</span> and remove it from the active user list.
            </>
          ) : ""
        }
        confirmText="Yes, deactivate user"
        isPending={deleteUserMutation.isPending}
        error={deleteUserMutation.error}
        onClose={() => setModal({ kind: "closed" })}
        onConfirm={() => {
          if (modal.kind === "delete") {
            setNotice(null)
            deleteUserMutation.mutate(modal.user.user_id)
          }
        }}
      />"""

content = content.replace(old_modal, new_modal)

with open("frontend/src/pages/Users.tsx", "w") as f:
    f.write(content)
