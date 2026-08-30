import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import Detections from "./Detections"
import type { AlertListResponse } from "@/api/alerts"
import type { CameraListResponse } from "@/api/cameras"
import { getAlerts, exportAlerts } from "@/api/alerts"
import { getCameras } from "@/api/cameras"
import { createExportJob } from "@/api/exports"
import { useAuthStore } from "@/store/useAuthStore"
import { useExportJobsStore } from "@/store/useExportJobsStore"

vi.mock("@/api/alerts", async () => {
  const actual = await vi.importActual<typeof import("@/api/alerts")>("@/api/alerts")
  return {
    ...actual,
    getAlerts: vi.fn(),
    getAlertDetails: vi.fn(),
    exportAlerts: vi.fn(),
    confirmAlert: vi.fn(),
    dismissAlert: vi.fn(),
    resolveAlert: vi.fn(),
    snoozeAlert: vi.fn(),
  }
})

vi.mock("@/api/cameras", async () => {
  const actual = await vi.importActual<typeof import("@/api/cameras")>("@/api/cameras")
  return { ...actual, getCameras: vi.fn() }
})

vi.mock("@/api/exports", async () => {
  const actual = await vi.importActual<typeof import("@/api/exports")>("@/api/exports")
  return { ...actual, createExportJob: vi.fn() }
})

const EMPTY_CAMERAS: CameraListResponse = {
  kpis: { total: 0, enabled: 0, network_connected: 0, active_detection: 0 },
  breakdowns: {
    connection: { connected: 0, disconnected: 0, reconnecting: 0, unresponsive: 0 },
    ai: { active: 0, inactive: 0, paused: 0, unresponsive: 0 },
  },
  total_filtered: 0,
  cameras: [],
}

const EMPTY_ALERTS: AlertListResponse = { total_filtered: 1, logs: [] }

const PHILIPPINE_FILTERS = {
  status: ["Resolved"],
  search: undefined,
  sort_by: "detected_at" as const,
  sort_order: "desc" as const,
  start_date: "2026-08-16T00:00:00+08:00",
  end_date: "2026-08-30T23:59:59.999999+08:00",
  camera_id: undefined,
  user_id: undefined,
}

function renderDetections() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Detections />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function setDateRangeAndStatus(user: ReturnType<typeof userEvent.setup>) {
  fireEvent.input(screen.getByLabelText("Filter incidents by date start"), {
    target: { value: "2026-08-16" },
  })
  fireEvent.input(screen.getByLabelText("Filter incidents by date end"), {
    target: { value: "2026-08-30" },
  })
  await user.click(screen.getByRole("button", { name: "All statuses" }))
  await user.click(screen.getByText("Resolved"))
}

describe("Detections date-filter export parity", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({ role: "Operator", username: "operator", userId: 1 })
    useExportJobsStore.setState({ jobs: [] })
    vi.mocked(getAlerts).mockResolvedValue(EMPTY_ALERTS)
    vi.mocked(getCameras).mockResolvedValue(EMPTY_CAMERAS)
    vi.mocked(exportAlerts).mockResolvedValue(undefined)
    vi.mocked(createExportJob).mockResolvedValue({ job_id: "job-1", status: "queued" })
  })

  it("uses committed Philippine date bounds for the list and CSV export", async () => {
    const user = userEvent.setup()
    renderDetections()

    await setDateRangeAndStatus(user)

    expect(screen.getByLabelText("Filter incidents by date start")).toHaveValue("2026-08-16")
    expect(screen.getByLabelText("Filter incidents by date end")).toHaveValue("2026-08-30")
    await waitFor(() =>
      expect(getAlerts).toHaveBeenLastCalledWith({ ...PHILIPPINE_FILTERS, limit: 10, offset: 0 }),
    )

    await user.click(screen.getByRole("button", { name: "Export" }))
    await user.click(screen.getByRole("menuitem", { name: /export as csv/i }))

    await waitFor(() => expect(exportAlerts).toHaveBeenCalledWith(PHILIPPINE_FILTERS, "csv"))
  })

  it("uses the same effective filters for an incident background export job", async () => {
    const user = userEvent.setup()
    vi.mocked(getAlerts).mockResolvedValue({ total_filtered: 60_000, logs: [] })
    renderDetections()

    await setDateRangeAndStatus(user)
    await user.click(screen.getByRole("button", { name: "Export" }))
    await user.click(screen.getByRole("button", { name: /run as a background job \(csv\)/i }))

    await waitFor(() =>
      expect(createExportJob).toHaveBeenCalledWith({
        report_type: "incidents",
        format: "csv",
        ...PHILIPPINE_FILTERS,
      }),
    )
  })

  it("clears dates from the next list request", async () => {
    const user = userEvent.setup()
    renderDetections()

    await setDateRangeAndStatus(user)
    await user.click(screen.getByRole("button", { name: "Clear" }))

    await waitFor(() =>
      expect(getAlerts).toHaveBeenLastCalledWith({
        status: undefined,
        search: undefined,
        sort_by: "detected_at",
        sort_order: "desc",
        start_date: undefined,
        end_date: undefined,
        camera_id: undefined,
        user_id: undefined,
        limit: 10,
        offset: 0,
      }),
    )

    await user.click(screen.getByRole("button", { name: "Export" }))
    await user.click(screen.getByRole("menuitem", { name: /export as csv/i }))

    await waitFor(() =>
      expect(exportAlerts).toHaveBeenCalledWith(
        {
          status: undefined,
          search: undefined,
          sort_by: "detected_at",
          sort_order: "desc",
          start_date: undefined,
          end_date: undefined,
          camera_id: undefined,
          user_id: undefined,
        },
        "csv",
      ),
    )
  })

  it("blocks export rather than sending an unfiltered reversed date range", async () => {
    const user = userEvent.setup()
    renderDetections()
    await user.click(screen.getByRole("button", { name: "Export" }))

    fireEvent.input(screen.getByLabelText("Filter incidents by date start"), {
      target: { value: "2026-08-31" },
    })
    fireEvent.input(screen.getByLabelText("Filter incidents by date end"), {
      target: { value: "2026-08-30" },
    })

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Start date must be on or before end date.",
    )
    expect(screen.getByRole("button", { name: "Export" })).toBeDisabled()
    await user.click(screen.getByRole("menuitem", { name: /export as csv/i }))
    expect(exportAlerts).not.toHaveBeenCalled()
    expect(createExportJob).not.toHaveBeenCalled()
    expect(getAlerts).not.toHaveBeenCalledWith(
      expect.objectContaining({
        start_date: "2026-08-31T00:00:00+08:00",
        end_date: "2026-08-30T23:59:59.999999+08:00",
      }),
    )
  })

  it("blocks a background job that was opened before the date range became invalid", async () => {
    const user = userEvent.setup()
    vi.mocked(getAlerts).mockResolvedValue({ total_filtered: 60_000, logs: [] })
    renderDetections()
    await waitFor(() => expect(getAlerts).toHaveBeenCalled())
    await user.click(screen.getByRole("button", { name: "Export" }))

    fireEvent.input(screen.getByLabelText("Filter incidents by date start"), {
      target: { value: "2026-08-31" },
    })
    fireEvent.input(screen.getByLabelText("Filter incidents by date end"), {
      target: { value: "2026-08-30" },
    })

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Start date must be on or before end date.",
    )
    await user.click(screen.getByRole("button", { name: /run as a background job \(csv\)/i }))
    expect(createExportJob).not.toHaveBeenCalled()
  })
})
