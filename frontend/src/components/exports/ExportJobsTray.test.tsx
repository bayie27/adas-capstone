import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ExportJobsTray } from "./ExportJobsTray"
import { useExportJobsStore } from "@/store/useExportJobsStore"

vi.mock("@/api/exports", async () => {
  const actual = await vi.importActual<typeof import("@/api/exports")>("@/api/exports")
  return {
    ...actual,
    getExportJob: vi.fn().mockResolvedValue({
      job_id: "job-1",
      report_type: "incidents",
      format: "csv",
      status: "queued",
      progress_current: 0,
      progress_total: null,
      failure_category: null,
      created_at: "2026-01-01T00:00:00Z",
      started_at: null,
      completed_at: null,
      expires_at: null,
    }),
    listExportJobs: vi.fn(),
  }
})

import { listExportJobs } from "@/api/exports"

function renderTray() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ExportJobsTray />
    </QueryClientProvider>,
  )
}

const HISTORY_JOB = {
  job_id: "job-earlier",
  report_type: "dashboard",
  format: "pdf",
  status: "completed",
  progress_current: 40,
  progress_total: 40,
  failure_category: null,
  created_at: "2025-12-01T00:00:00Z",
  started_at: "2025-12-01T00:00:01Z",
  completed_at: "2025-12-01T00:00:05Z",
  expires_at: "2025-12-04T00:00:05Z",
}

describe("ExportJobsTray", () => {
  beforeEach(() => {
    useExportJobsStore.setState({
      jobs: [
        {
          jobId: "job-1",
          reportType: "incidents",
          format: "csv",
          createdAt: "2026-01-01T00:00:00Z",
        },
      ],
    })
    vi.mocked(listExportJobs).mockReset()
  })

  it("does not render the trigger button when there are no tracked jobs", () => {
    useExportJobsStore.setState({ jobs: [] })
    renderTray()
    expect(screen.queryByRole("button", { name: /export jobs/i })).not.toBeInTheDocument()
  })

  it("renders the trigger button when tracked jobs exist", () => {
    renderTray()
    expect(screen.getByRole("button", { name: /export jobs/i })).toBeInTheDocument()
  })

  it("fetches and renders account-wide history on demand, deduplicated against the tracked session list", async () => {
    vi.mocked(listExportJobs).mockResolvedValue({
      total_filtered: 2,
      items: [HISTORY_JOB, { ...HISTORY_JOB, job_id: "job-1" }] as never,
    })
    const user = userEvent.setup()
    renderTray()

    await user.click(screen.getByRole("button", { name: /export jobs/i }))
    await user.click(screen.getByRole("button", { name: /load history from other sessions/i }))

    await waitFor(() => expect(listExportJobs).toHaveBeenCalledWith({ limit: 20, offset: 0 }))
    expect(await screen.findByText("Dashboard")).toBeInTheDocument()
    // job-1 is already in "This session" -- deduplicated out of history.
    expect(screen.getAllByText("Incident log")).toHaveLength(1)
  })

  it("shows an empty state when the account has no earlier-session exports", async () => {
    vi.mocked(listExportJobs).mockResolvedValue({ total_filtered: 0, items: [] })
    const user = userEvent.setup()
    renderTray()
    await user.click(screen.getByRole("button", { name: /export jobs/i }))
    await user.click(screen.getByRole("button", { name: /load history from other sessions/i }))
    expect(await screen.findByText("No earlier exports.")).toBeInTheDocument()
  })

  it("shows an inline error with retry when the history fetch fails", async () => {
    vi.mocked(listExportJobs).mockRejectedValueOnce(new Error("network down"))
    const user = userEvent.setup()
    renderTray()
    await user.click(screen.getByRole("button", { name: /export jobs/i }))
    await user.click(screen.getByRole("button", { name: /load history from other sessions/i }))
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument()
  })

  it("shows Load more only when more history remains, and fetches the next page", async () => {
    vi.mocked(listExportJobs).mockResolvedValueOnce({
      total_filtered: 2,
      items: [HISTORY_JOB] as never,
    })
    const user = userEvent.setup()
    renderTray()
    await user.click(screen.getByRole("button", { name: /export jobs/i }))
    await user.click(screen.getByRole("button", { name: /load history from other sessions/i }))
    await screen.findByText("Dashboard")

    vi.mocked(listExportJobs).mockResolvedValueOnce({
      total_filtered: 2,
      items: [{ ...HISTORY_JOB, job_id: "job-earlier-2" }] as never,
    })
    await user.click(screen.getByRole("button", { name: /load more/i }))
    await waitFor(() => expect(listExportJobs).toHaveBeenCalledWith({ limit: 20, offset: 20 }))
    expect(screen.queryByRole("button", { name: /load more/i })).not.toBeInTheDocument()
  })
})
