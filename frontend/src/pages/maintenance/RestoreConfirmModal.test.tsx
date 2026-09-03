import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import type { BackupRead } from "@/api/maintenance"
import { RestoreConfirmModal } from "./RestoreConfirmModal"

const BACKUP_ID = "0123456789abcdef0123456789abcdef"
const backup: BackupRead = {
  backup_id: BACKUP_ID,
  created_at: "2026-08-26T05:30:00+00:00",
  origin: "manual",
  file_size: 2048,
  valid: true,
  checks: { checksum: true, quick_check: true, foreign_key_check: true },
  storage_tier: "protected",
  storage_reason: null,
}

function renderModal() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <RestoreConfirmModal backup={backup} onClose={vi.fn()} onSuccess={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe("RestoreConfirmModal", () => {
  it("repeats the exact selected backup metadata", () => {
    renderModal()
    expect(screen.getByText("Manual backup")).toBeInTheDocument()
    expect(screen.getByText("2.0 KB")).toBeInTheDocument()
    expect(screen.getByText("Valid")).toBeInTheDocument()
    expect(screen.getByText("01234567…abcdef")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Copy full backup ID" })).toBeInTheDocument()
  })

  it("never pre-fills the confirmation field", () => {
    renderModal()
    expect(screen.getByLabelText('Type "RESTORE DATABASE" to confirm')).toHaveValue("")
  })

  it("describes the automatic restart", () => {
    renderModal()
    expect(screen.getByText(/system will restart automatically/i)).toBeInTheDocument()
  })

  it("keeps the submit button disabled until both the password and exact confirmation are present", async () => {
    const user = userEvent.setup()
    renderModal()

    const confirmationField = screen.getByLabelText('Type "RESTORE DATABASE" to confirm')
    const submit = screen.getByRole("button", { name: /restore database/i })
    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText(/current password/i), "hunter2")
    expect(submit).toBeDisabled()

    await user.type(confirmationField, "RESTORE DATABASE!")
    expect(submit).toBeDisabled()

    await user.clear(confirmationField)
    await user.type(confirmationField, "RESTORE DATABASE")
    expect(submit).toBeEnabled()
  })

  it("stays disabled on a case or whitespace mismatch", async () => {
    const user = userEvent.setup()
    renderModal()

    await user.type(screen.getByLabelText(/current password/i), "hunter2")
    await user.type(
      screen.getByLabelText('Type "RESTORE DATABASE" to confirm'),
      "restore database ",
    )

    expect(screen.getByRole("button", { name: /restore database/i })).toBeDisabled()
  })
})
