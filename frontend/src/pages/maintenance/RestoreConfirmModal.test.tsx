import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { RestoreConfirmModal } from "./RestoreConfirmModal"

function renderModal() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <RestoreConfirmModal backupId="abc123" onClose={vi.fn()} onSuccess={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe("RestoreConfirmModal", () => {
  it("never pre-fills the confirmation field", () => {
    renderModal()
    expect(screen.getByLabelText(/type "restore abc123" to confirm/i)).toHaveValue("")
  })

  it("states the real manual next step instead of claiming an automatic shutdown", () => {
    renderModal()
    expect(screen.getByText(/nothing happens automatically/i)).toBeInTheDocument()
    expect(screen.getByText(/python -m app\.maintenance restore abc123/i)).toBeInTheDocument()
    expect(screen.queryByText(/will go offline shortly/i)).not.toBeInTheDocument()
  })

  it("keeps the submit button disabled until both the password and the exact confirmation are present", async () => {
    const user = userEvent.setup()
    renderModal()

    const submit = screen.getByRole("button", { name: /request restore/i })
    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText(/current password/i), "hunter2")
    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText(/type "restore abc123" to confirm/i), "RESTORE wrong-id")
    expect(submit).toBeDisabled()

    await user.clear(screen.getByLabelText(/type "restore abc123" to confirm/i))
    await user.type(screen.getByLabelText(/type "restore abc123" to confirm/i), "RESTORE abc123")
    expect(submit).toBeEnabled()
  })

  it("stays disabled on a case or whitespace mismatch", async () => {
    const user = userEvent.setup()
    renderModal()

    await user.type(screen.getByLabelText(/current password/i), "hunter2")
    await user.type(screen.getByLabelText(/type "restore abc123" to confirm/i), "restore abc123 ")

    expect(screen.getByRole("button", { name: /request restore/i })).toBeDisabled()
  })
})
