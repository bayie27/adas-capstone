import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import Maintenance from "./Maintenance"
import type { BackupRead, MaintenanceStatusRead } from "@/api/maintenance"

vi.mock("@/api/maintenance", async () => {
  const actual = await vi.importActual<typeof import("@/api/maintenance")>("@/api/maintenance")
  return {
    ...actual,
    getBackups: vi.fn(),
    getLatestRestore: vi.fn().mockResolvedValue(null),
    getMaintenanceStatus: vi.fn(),
    triggerBackup: vi.fn(),
    requestRestore: vi.fn(),
  }
})

import { getBackups, getMaintenanceStatus, requestRestore } from "@/api/maintenance"

const VALID_ID = "0123456789abcdef0123456789abcdef"
const INVALID_ID = "fedcba9876543210fedcba9876543210"

const mockBackups: BackupRead[] = [
  {
    backup_id: VALID_ID,
    file_size: 1048576,
    created_at: "2026-08-25T10:00:00Z",
    origin: "manual",
    valid: true,
    checks: { checksum: true, quick_check: true, foreign_key_check: true },
  },
  {
    backup_id: INVALID_ID,
    file_size: 512,
    created_at: "2026-08-24T10:00:00Z",
    origin: "scheduled",
    valid: false,
    checks: { checksum: false, quick_check: true, foreign_key_check: true },
  },
]

const availableStatus: MaintenanceStatusRead = {
  last_scheduled_backup: null,
  last_manual_backup: null,
  next_scheduled_backup_at: null,
  backup_overdue: false,
  maintenance_hour_local: 3,
  maintenance_timezone: "Asia/Manila",
  last_restart: null,
  latest_restore: null,
  restore_coordinator: {
    available: true,
    state: "idle",
    platform: "windows",
    last_seen_at: "2026-08-25T10:00:00Z",
    reason: null,
  },
}

function renderMaintenance() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <Maintenance />
    </QueryClientProvider>,
  )
}

describe("Maintenance page restore point picker", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getBackups).mockResolvedValue({ total_filtered: 2, items: mockBackups })
    vi.mocked(getMaintenanceStatus).mockResolvedValue(availableStatus)
  })

  it("requires expanding a valid row and repeats its metadata in the confirmation modal", async () => {
    const user = userEvent.setup()
    renderMaintenance()

    expect(await screen.findByRole("row", { name: /2026.*1\.0 MB.*Valid/i })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Restore this backup…" })).not.toBeInTheDocument()

    await user.click(await screen.findByRole("row", { name: /2026.*1\.0 MB.*Valid/i }))
    const restoreTrigger = screen.getByRole("button", { name: "Restore this backup…" })
    expect(restoreTrigger).toBeEnabled()

    await user.click(restoreTrigger)
    expect(screen.getByRole("heading", { name: "Restore database" })).toBeInTheDocument()
    expect(screen.getAllByText("Manual backup").length).toBeGreaterThan(0)
    expect(screen.getAllByText("1.0 MB").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Valid").length).toBeGreaterThan(0)
    expect(screen.getByText("01234567…abcdef")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Copy full backup ID" })).toBeInTheDocument()
  })

  it("submits the row selected by the administrator", async () => {
    const secondBackup = { ...mockBackups[1], valid: true, checks: { checksum: true } }
    vi.mocked(getBackups).mockResolvedValue({
      total_filtered: 2,
      items: [mockBackups[0], secondBackup],
    })
    vi.mocked(requestRestore).mockResolvedValue({
      detail: "Restore accepted. The system will restart automatically.",
      backup_id: INVALID_ID,
      request_id: "a".repeat(32),
      status: "requested",
    })
    const user = userEvent.setup()
    renderMaintenance()

    await user.click(await screen.findByRole("row", { name: /2026.*512 B.*Valid/i }))
    await user.click(screen.getByRole("button", { name: "Restore this backup…" }))
    await user.type(screen.getByLabelText(/current password/i), "hunter2")
    await user.type(screen.getByLabelText('Type "RESTORE DATABASE" to confirm'), "RESTORE DATABASE")
    await user.click(screen.getByRole("button", { name: "Restore database" }))

    await waitFor(() => {
      expect(requestRestore).toHaveBeenCalledTimes(1)
      expect(requestRestore).toHaveBeenCalledWith(
        {
          backup_id: INVALID_ID,
          current_password: "hunter2",
          confirmation: "RESTORE DATABASE",
        },
        expect.any(Object),
      )
    })
  })

  it("keeps an invalid backup inspectable without a restore action", async () => {
    const user = userEvent.setup()
    renderMaintenance()

    await user.click(await screen.findByRole("row", { name: /2026.*512 B.*Invalid/i }))

    expect(screen.getByText("Validation Checks:")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Restore this backup…" })).not.toBeInTheDocument()
  })

  it("disables the valid-row action when the supervised service is unavailable", async () => {
    vi.mocked(getMaintenanceStatus).mockResolvedValue({
      ...availableStatus,
      restore_coordinator: {
        ...availableStatus.restore_coordinator,
        available: false,
        state: "unavailable",
        reason: "stale",
      },
    })
    const user = userEvent.setup()
    renderMaintenance()

    await user.click(await screen.findByRole("row", { name: /2026.*1\.0 MB.*Valid/i }))

    expect(screen.getByRole("button", { name: "Restore this backup…" })).toBeDisabled()
    expect(
      screen.getAllByText(
        "Automatic restore is unavailable because the maintenance service is not running.",
      ).length,
    ).toBeGreaterThan(0)
  })
})
