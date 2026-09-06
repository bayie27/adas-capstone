import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import Dashboard from "./Dashboard"
import type { DashboardAnalyticsResponse } from "@/api/analytics"

vi.mock("@/api/analytics", async () => {
  const actual = await vi.importActual<typeof import("@/api/analytics")>("@/api/analytics")
  return { ...actual, getDashboardAnalytics: vi.fn() }
})
vi.mock("@/api/cameras", async () => {
  const actual = await vi.importActual<typeof import("@/api/cameras")>("@/api/cameras")
  return { ...actual, getCameras: vi.fn().mockResolvedValue({ cameras: [] }) }
})
import { getDashboardAnalytics } from "@/api/analytics"

function response(kpis: DashboardAnalyticsResponse["kpis"]): DashboardAnalyticsResponse {
  return { kpis, frequency_by_location: [], peak_accident_times: [] }
}

function renderDashboard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <Dashboard />
    </QueryClientProvider>,
  )
}

describe("Dashboard KPI delta badges", () => {
  it("renders no badge at all for a null delta -- the default all-time load", async () => {
    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 3,
        total_accidents: 10,
        total_cleared: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: null,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()
    expect(await screen.findByText("Ongoing Accidents")).toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })

  it("more accidents (positive delta) reads as bad news -- danger tone despite the + sign", async () => {
    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 3,
        total_accidents: 10,
        total_cleared: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: 12.5,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()
    const delta = await screen.findByText("+12.5%")
    expect(delta).toHaveClass("text-danger")
  })

  it("more cleared (positive delta) reads as good news -- success tone", async () => {
    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 3,
        total_accidents: 10,
        total_cleared: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: null,
        total_cleared_delta_pct: 8,
      }),
    )
    renderDashboard()
    const delta = await screen.findByText("+8.0%")
    expect(delta).toHaveClass("text-success")
  })

  it("more ongoing (positive delta) reads as bad news -- danger tone, same as total_accidents", async () => {
    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 5,
        total_accidents: 10,
        total_cleared: 7,
        ongoing_delta_pct: 20,
        total_accidents_delta_pct: null,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()
    const delta = await screen.findByText("+20.0%")
    expect(delta).toHaveClass("text-danger")
  })

  it("fewer accidents (negative delta) reads as good news -- success tone with a minus sign", async () => {
    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 3,
        total_accidents: 10,
        total_cleared: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: -5,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()
    const delta = await screen.findByText("−5.0%")
    expect(delta).toHaveClass("text-success")
  })

  it("renders an exact-zero delta as a neutral 0%, not success or danger", async () => {
    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 3,
        total_accidents: 10,
        total_cleared: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: 0,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()
    const delta = await screen.findByText("0%")
    expect(delta).not.toHaveClass("text-danger")
    expect(delta).not.toHaveClass("text-success")
  })
})

describe("Dashboard KPI delta caption", () => {
  it("captions a delta with the default 7-day comparison window", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date("2026-09-05T04:00:00Z"))

    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 3,
        total_accidents: 10,
        total_cleared: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: 12.5,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()

    expect(await screen.findByText("vs previous 7 days")).toBeInTheDocument()

    vi.useRealTimers()
  })

  it("omits the caption when there is no delta to explain", async () => {
    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 3,
        total_accidents: 10,
        total_cleared: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: null,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()

    // The static description still renders on its own -- the caption is
    // additive, not a replacement.
    expect(await screen.findByText("Live incident queue")).toBeInTheDocument()
    expect(screen.queryByText(/vs previous/)).not.toBeInTheDocument()
  })

  it("keeps a KPI's own description alongside the delta caption", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date("2026-09-05T04:00:00Z"))

    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 5,
        total_accidents: 10,
        total_cleared: 7,
        ongoing_delta_pct: 20,
        total_accidents_delta_pct: null,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()

    expect(await screen.findByText("Live incident queue")).toBeInTheDocument()
    expect(await screen.findByText("vs previous 7 days")).toBeInTheDocument()

    vi.useRealTimers()
  })

  it("follows the operator's own range, not a fixed 7", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date("2026-08-20T04:00:00Z"))
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })

    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 3,
        total_accidents: 10,
        total_cleared: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: 12.5,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()

    await user.click(screen.getByRole("button", { name: "Filter analytics by date" }))
    await user.click(screen.getByRole("button", { name: "Custom range" }))
    await user.click(screen.getByRole("button", { name: "August 16, 2026" }))
    await user.click(screen.getByRole("button", { name: "August 30, 2026" }))
    await user.click(screen.getByRole("button", { name: "Apply" }))

    // August 16 through August 30 inclusive is 15 days, not the default 7.
    expect(await screen.findByText("vs previous 15 days")).toBeInTheDocument()

    vi.useRealTimers()
  })
})

describe("Dashboard date-filter API bounds", () => {
  it("defaults to the last 7 days on first load, with no interaction", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date("2026-09-05T04:00:00Z"))

    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 0,
        total_accidents: 0,
        total_cleared: 0,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: null,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()

    await waitFor(() =>
      expect(getDashboardAnalytics).toHaveBeenCalledWith(
        expect.objectContaining({
          start_date: "2026-08-30T00:00:00+08:00",
          end_date: "2026-09-05T23:59:59.999999+08:00",
        }),
      ),
    )
    expect(
      await screen.findByRole("button", { name: "Filter analytics by date" }),
    ).toHaveTextContent("Last 7 days")

    vi.useRealTimers()
  })

  it("sends full Philippine day-boundary instants, not bare calendar dates", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date("2026-08-20T04:00:00Z"))
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })

    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 0,
        total_accidents: 0,
        total_cleared: 0,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: null,
        total_cleared_delta_pct: null,
      }),
    )
    renderDashboard()

    await user.click(screen.getByRole("button", { name: "Filter analytics by date" }))
    await user.click(screen.getByRole("button", { name: "Custom range" }))
    await user.click(screen.getByRole("button", { name: "August 16, 2026" }))
    await user.click(screen.getByRole("button", { name: "August 30, 2026" }))
    await user.click(screen.getByRole("button", { name: "Apply" }))

    await waitFor(() =>
      expect(getDashboardAnalytics).toHaveBeenLastCalledWith(
        expect.objectContaining({
          start_date: "2026-08-16T00:00:00+08:00",
          end_date: "2026-08-30T23:59:59.999999+08:00",
        }),
      ),
    )

    vi.useRealTimers()
  })
})
