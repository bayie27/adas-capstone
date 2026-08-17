import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
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
        total_resolved: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: null,
        total_resolved_delta_pct: null,
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
        total_resolved: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: 12.5,
        total_resolved_delta_pct: null,
      }),
    )
    renderDashboard()
    const delta = await screen.findByText("+12.5%")
    expect(delta).toHaveClass("text-danger")
  })

  it("more resolved (positive delta) reads as good news -- success tone", async () => {
    vi.mocked(getDashboardAnalytics).mockResolvedValue(
      response({
        ongoing: 3,
        total_accidents: 10,
        total_resolved: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: null,
        total_resolved_delta_pct: 8,
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
        total_resolved: 7,
        ongoing_delta_pct: 20,
        total_accidents_delta_pct: null,
        total_resolved_delta_pct: null,
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
        total_resolved: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: -5,
        total_resolved_delta_pct: null,
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
        total_resolved: 7,
        ongoing_delta_pct: null,
        total_accidents_delta_pct: 0,
        total_resolved_delta_pct: null,
      }),
    )
    renderDashboard()
    const delta = await screen.findByText("0%")
    expect(delta).not.toHaveClass("text-danger")
    expect(delta).not.toHaveClass("text-success")
  })
})
