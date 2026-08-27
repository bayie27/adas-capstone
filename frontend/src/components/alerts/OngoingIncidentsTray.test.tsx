import { act, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { OngoingIncidentsTray } from "./OngoingIncidentsTray"
import { renderWithProviders } from "@/test/wrapper"
import { useAlertStore } from "@/store/useAlertStore"
import * as alertsApi from "@/api/alerts"
import type { AlertLog } from "@/api/alerts"

vi.mock("@/api/alerts", async () => {
  const actual = await vi.importActual<typeof import("@/api/alerts")>("@/api/alerts")
  return {
    ...actual,
    resolveAlert: vi.fn(),
    dismissAlert: vi.fn(),
  }
})

const mockOngoingAlert: AlertLog = {
  log_id: 201,
  source_event_id: "evt-201",
  camera_id: 2,
  detected_at: "2026-08-27T10:00:00Z",
  confidence_score: 0.88,
  detection_status: "Ongoing",
  snapshot_url: "https://example.com/ongoing.jpg",
  verified_by_id: 1,
  verified_by_name: "Lead Operator",
  verified_at: "2026-08-27T10:01:00Z",
  closed_by_id: null,
  closed_by_name: null,
  closed_at: null,
  snoozed_at: null,
  snoozed_until: null,
  snoozed_by_id: null,
  camera_name: "Highway Intersection",
  created_at: "2026-08-27T10:00:00Z",
  updated_at: "2026-08-27T10:01:00Z",
}

describe("OngoingIncidentsTray", () => {
  beforeEach(() => {
    useAlertStore.getState().clearAlerts()
    vi.clearAllMocks()
  })

  it("renders nothing when there are no ongoing incidents", () => {
    render(renderWithProviders(<OngoingIncidentsTray />))
    expect(
      screen.queryByRole("button", { name: /ongoing incidents tray/i }),
    ).not.toBeInTheDocument()
  })

  it("renders the floating tray button when ongoing incidents exist", () => {
    useAlertStore.setState({ alerts: [mockOngoingAlert] })
    render(renderWithProviders(<OngoingIncidentsTray />))

    const trayBtn = screen.getByRole("button", { name: /ongoing incidents tray/i })
    expect(trayBtn).toBeInTheDocument()
    expect(trayBtn).toHaveTextContent("ONGOING")
    expect(trayBtn).toHaveTextContent("1")
  })

  it("opens the side panel when floating tray button is clicked", async () => {
    const user = userEvent.setup()
    useAlertStore.setState({ alerts: [mockOngoingAlert] })
    render(renderWithProviders(<OngoingIncidentsTray />))

    const trayBtn = screen.getByRole("button", { name: /ongoing incidents tray/i })
    await user.click(trayBtn)

    expect(screen.getByText("Ongoing Incidents")).toBeInTheDocument()
    expect(screen.getByText("Highway Intersection")).toBeInTheDocument()
    expect(screen.getByText("88.0%")).toBeInTheDocument()
    expect(screen.getByText(/verified by lead operator/i)).toBeInTheDocument()
  })

  it("opens IncidentDetailModal and allows resolving the ongoing incident", async () => {
    const user = userEvent.setup()
    vi.mocked(alertsApi.resolveAlert).mockResolvedValueOnce({
      ...mockOngoingAlert,
      detection_status: "Resolved",
      closed_by_name: "Current User",
      closed_at: "2026-08-27T10:05:00Z",
    })

    useAlertStore.setState({ alerts: [mockOngoingAlert] })
    render(renderWithProviders(<OngoingIncidentsTray />))

    // Open tray
    await user.click(screen.getByRole("button", { name: /ongoing incidents tray/i }))

    // Click Review & Resolve
    const reviewBtn = screen.getByRole("button", { name: /review & resolve/i })
    await user.click(reviewBtn)

    // Modal opens
    expect(screen.getByRole("button", { name: /resolve accident/i })).toBeInTheDocument()

    // Click Resolve Accident
    await user.click(screen.getByRole("button", { name: /resolve accident/i }))

    await waitFor(() => {
      expect(alertsApi.resolveAlert).toHaveBeenCalledWith(201)
    })

    // Incident is removed from ongoing queue and tray disappears
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /ongoing incidents tray/i }),
      ).not.toBeInTheDocument()
    })
  })

  it("removes incident from tray in real-time when another operator resolves it", () => {
    useAlertStore.setState({ alerts: [mockOngoingAlert] })
    const { rerender } = render(renderWithProviders(<OngoingIncidentsTray />))

    expect(screen.getByRole("button", { name: /ongoing incidents tray/i })).toBeInTheDocument()

    // Simulate WebSocket update removing or changing to Resolved
    act(() => {
      useAlertStore.getState().addAlert({
        ...mockOngoingAlert,
        detection_status: "Resolved",
        closed_by_name: "Other Operator",
        updated_at: "2026-08-27T10:06:00Z",
      })
    })

    rerender(renderWithProviders(<OngoingIncidentsTray />))
    expect(
      screen.queryByRole("button", { name: /ongoing incidents tray/i }),
    ).not.toBeInTheDocument()
  })
})
