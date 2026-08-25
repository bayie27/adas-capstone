import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import Maintenance from "./Maintenance"
import type { BackupRead } from "@/api/maintenance"

vi.mock("@/api/maintenance", async () => {
  const actual = await vi.importActual<typeof import("@/api/maintenance")>("@/api/maintenance")
  return {
    ...actual,
    getBackups: vi.fn(),
    getLatestRestore: vi.fn().mockResolvedValue(null),
    triggerBackup: vi.fn(),
    requestRestore: vi.fn(),
  }
})

import { getBackups } from "@/api/maintenance"

const mockBackups: BackupRead[] = [
  {
    backup_id: "bk-2026-08-25",
    file_size: 1048576,
    created_at: "2026-08-25T10:00:00Z",
    origin: "manual",
    valid: true,
    checks: {
      integrity: true,
      schema: true,
      data: true,
    },
  },
]

function renderMaintenance() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <Maintenance />
    </QueryClientProvider>,
  )
}

describe("Maintenance Page Backup Row & Restore Trigger", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders backup row and reveals destructive restore button and validation badges upon expansion", async () => {
    const user = userEvent.setup()
    vi.mocked(getBackups).mockResolvedValue({
      total_filtered: 1,
      items: mockBackups,
    })

    renderMaintenance()

    expect(await screen.findByText("bk-2026-08-25")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /request restore/i })).not.toBeInTheDocument()

    // Click row to expand
    await user.click(screen.getByText("bk-2026-08-25"))

    // Validation checks should be visible
    expect(screen.getByText("Validation Checks:")).toBeInTheDocument()

    // Bounded danger restore button should be visible
    const restoreTrigger = screen.getByRole("button", { name: "Request Restore" })
    expect(restoreTrigger).toBeInTheDocument()
    expect(restoreTrigger).toHaveClass("bg-danger")

    // Clicking trigger opens the modal
    await user.click(restoreTrigger)
    expect(screen.getByText(/Backup bk-2026-08-25/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/type "restore bk-2026-08-25" to confirm/i)).toBeInTheDocument()
  })
})
