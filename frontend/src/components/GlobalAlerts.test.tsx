import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { GlobalAlerts } from "./GlobalAlerts"
import { renderWithProviders } from "@/test/wrapper"
import { useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
import * as alertsApi from "@/api/alerts"
import type { AlertLog } from "@/api/alerts"

vi.mock("@/api/alerts", async () => {
  const actual = await vi.importActual<typeof import("@/api/alerts")>("@/api/alerts")
  return {
    ...actual,
    snoozeAlert: vi.fn(),
    dismissAlert: vi.fn(),
    confirmAlert: vi.fn(),
    resolveAlert: vi.fn(),
  }
})

const mockAlert: AlertLog = {
  log_id: 101,
  source_event_id: "evt-101",
  camera_id: 1,
  detected_at: "2026-08-25T10:00:00Z",
  confidence_score: 0.95,
  detection_status: "Unverified",
  snapshot_url: "https://example.com/snapshot.jpg",
  verified_by_id: null,
  verified_at: null,
  closed_by_id: null,
  closed_at: null,
  snoozed_at: null,
  snoozed_until: null,
  snoozed_by_id: null,
  camera_name: "Front Gate Cam",
  verified_by_name: null,
  closed_by_name: null,
  created_at: "2026-08-25T10:00:00Z",
  updated_at: "2026-08-25T10:00:00Z",
}

describe("GlobalAlerts", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAlertStore.setState({
      alerts: [],
      snoozedUntil: {},
      snoozedBy: {},
      handledByOther: {},
    })
    useAuthStore.setState({ username: "testoperator" })
  })

  it("renders nothing when there are no alerts", () => {
    render(renderWithProviders(<GlobalAlerts />))
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })

  it("renders the Accident Detected modal for unverified alerts", () => {
    useAlertStore.setState({ alerts: [mockAlert] })
    render(renderWithProviders(<GlobalAlerts />))
    expect(screen.getByRole("alertdialog")).toBeInTheDocument()
    expect(screen.getByText("Accident Detected")).toBeInTheDocument()
    expect(screen.getByText("Front Gate Cam")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /snooze alarm/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /dismiss accident/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /confirm accident/i })).toBeInTheDocument()
  })

  it("clicking snooze mutes the alarm without closing the modal and updates icon to muted", async () => {
    const user = userEvent.setup()
    const futureDate = new Date(Date.now() + 60_000).toISOString()
    vi.mocked(alertsApi.snoozeAlert).mockResolvedValueOnce({
      ...mockAlert,
      snoozed_until: futureDate,
    })

    useAlertStore.setState({ alerts: [mockAlert] })
    render(renderWithProviders(<GlobalAlerts />))

    const snoozeButton = screen.getByRole("button", { name: /snooze alarm/i })
    expect(snoozeButton).not.toBeDisabled()

    await user.click(snoozeButton)

    await waitFor(() => {
      expect(alertsApi.snoozeAlert).toHaveBeenCalledWith(101)
    })

    // Modal stays open and visible on screen
    expect(screen.getByRole("alertdialog")).toBeInTheDocument()
    expect(screen.getByText("Accident Detected")).toBeInTheDocument()

    // Button updates to muted state with muted title and is disabled
    const mutedButton = screen.getByRole("button", { name: /alarm muted/i })
    expect(mutedButton).toBeInTheDocument()
    expect(mutedButton).toBeDisabled()
  })

  it("clicking dismiss accident removes alert from store and closes modal", async () => {
    const user = userEvent.setup()
    vi.mocked(alertsApi.dismissAlert).mockResolvedValueOnce({
      ...mockAlert,
      detection_status: "Dismissed",
    })

    useAlertStore.setState({ alerts: [mockAlert] })
    render(renderWithProviders(<GlobalAlerts />))

    const dismissBtn = screen.getByRole("button", { name: /dismiss accident/i })
    await user.click(dismissBtn)

    await waitFor(() => {
      expect(alertsApi.dismissAlert).toHaveBeenCalledWith(101)
    })

    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
    })
  })

  it("clicking confirm accident calls confirmAlert and closes modal", async () => {
    const user = userEvent.setup()
    vi.mocked(alertsApi.confirmAlert).mockResolvedValueOnce({
      ...mockAlert,
      detection_status: "Ongoing",
    })

    useAlertStore.setState({ alerts: [mockAlert] })
    render(renderWithProviders(<GlobalAlerts />))

    const confirmBtn = screen.getByRole("button", { name: /confirm accident/i })
    await user.click(confirmBtn)

    await waitFor(() => {
      expect(alertsApi.confirmAlert).toHaveBeenCalledWith(101)
    })

    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
    })
  })
})
