import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
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
  }
})

function renderTray() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ExportJobsTray />
    </QueryClientProvider>,
  )
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
  })

  it("renders nothing when there are no tracked jobs", () => {
    useExportJobsStore.setState({ jobs: [] })
    renderTray()
    expect(screen.queryByRole("button", { name: /export jobs/i })).not.toBeInTheDocument()
  })

  it("states the browser-only scope and shells the cross-session fetch as a disabled affordance", async () => {
    const user = userEvent.setup()
    renderTray()

    await user.click(screen.getByRole("button", { name: /export jobs/i }))

    expect(screen.getByText("Showing exports started from this browser only.")).toBeInTheDocument()

    const loadHistoryButton = screen.getByRole("button", {
      name: /load history from other sessions/i,
    })
    expect(loadHistoryButton).toBeDisabled()
    expect(screen.getByText("Unavailable")).toBeInTheDocument()
  })
})
