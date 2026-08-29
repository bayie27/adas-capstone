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
    useAlertStore.getState().clearAlerts()
    vi.clearAllMocks()
    useAuthStore.setState({ username: "testoperator" })
  })

  it("renders nothing when there are no alerts", () => {
    render(renderWithProviders(<GlobalAlerts />))
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })

  it("renders nothing when only ongoing alerts exist", () => {
    useAlertStore.setState({
      alerts: [
        {
          ...mockAlert,
          detection_status: "Ongoing",
        },
      ],
    })
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

  it("clicking snooze mutes the alarm and disables the snooze button until duration expires", async () => {
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

    // Click to snooze (mute)
    await user.click(snoozeButton)

    await waitFor(() => {
      expect(alertsApi.snoozeAlert).toHaveBeenCalledWith(101)
    })

    // Modal stays open and visible on screen
    expect(screen.getByRole("alertdialog")).toBeInTheDocument()
    expect(screen.getByText("Accident Detected")).toBeInTheDocument()

    // Button updates to snoozed state and is disabled (cannot be unmuted manually)
    await waitFor(() => {
      const snoozedBtn = screen.getByRole("button", { name: /alarms snoozed/i })
      expect(snoozedBtn).toBeInTheDocument()
      expect(snoozedBtn).toBeDisabled()
    })
  })

  it("clicking snooze when multiple unverified alerts are active snoozes all of them simultaneously", async () => {
    const user = userEvent.setup()
    const futureDate = new Date(Date.now() + 60_000).toISOString()
    const mockAlert2: AlertLog = {
      ...mockAlert,
      log_id: 102,
      camera_name: "Rear Exit Cam",
    }
    vi.mocked(alertsApi.snoozeAlert).mockImplementation(async (id: number) => ({
      ...mockAlert,
      log_id: id,
      snoozed_until: futureDate,
    }))

    useAlertStore.setState({ alerts: [mockAlert, mockAlert2] })
    render(renderWithProviders(<GlobalAlerts />))

    const snoozeButton = screen.getByRole("button", { name: /snooze alarm/i })
    expect(snoozeButton).not.toBeDisabled()

    // Click snooze
    await user.click(snoozeButton)

    await waitFor(() => {
      expect(alertsApi.snoozeAlert).toHaveBeenCalledWith(101)
      expect(alertsApi.snoozeAlert).toHaveBeenCalledWith(102)
    })

    // Both should be in snoozed store
    expect(useAlertStore.getState().snoozedUntil[101]).toBe(futureDate)
    expect(useAlertStore.getState().snoozedUntil[102]).toBe(futureDate)
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

  it("renders navigation arrows and counter when multiple alerts are queued, and allows cycling", async () => {
    const user = userEvent.setup()
    const mockAlert2: AlertLog = {
      ...mockAlert,
      log_id: 102,
      camera_name: "Rear Exit Cam",
    }

    useAlertStore.setState({ alerts: [mockAlert, mockAlert2] })
    render(renderWithProviders(<GlobalAlerts />))

    expect(screen.getByText("Alert 1 of 2")).toBeInTheDocument()
    expect(screen.getByText("Front Gate Cam")).toBeInTheDocument()

    const prevBtn = screen.getByRole("button", { name: /previous alert/i })
    const nextBtn = screen.getByRole("button", { name: /next alert/i })

    expect(prevBtn).toBeDisabled()
    expect(nextBtn).not.toBeDisabled()

    // Navigate to next alert
    await user.click(nextBtn)

    expect(screen.getByText("Alert 2 of 2")).toBeInTheDocument()
    expect(screen.getByText("Rear Exit Cam")).toBeInTheDocument()
    expect(nextBtn).toBeDisabled()
    expect(prevBtn).not.toBeDisabled()

    // Navigate back via keyboard ArrowLeft
    await user.keyboard("{ArrowLeft}")

    expect(screen.getByText("Alert 1 of 2")).toBeInTheDocument()
    expect(screen.getByText("Front Gate Cam")).toBeInTheDocument()

    // Navigate forward via keyboard ArrowRight
    await user.keyboard("{ArrowRight}")

    expect(screen.getByText("Alert 2 of 2")).toBeInTheDocument()
    expect(screen.getByText("Rear Exit Cam")).toBeInTheDocument()
  })

  it("renders telemetry labels (TIMESTAMP, CAMERA NAME, AI-CONFIDENCE SCORE) and snapshot image", () => {
    useAlertStore.setState({ alerts: [mockAlert] })
    render(renderWithProviders(<GlobalAlerts />))

    expect(screen.getByText("TIMESTAMP")).toBeInTheDocument()
    expect(screen.getByText("CAMERA NAME")).toBeInTheDocument()
    expect(screen.getByText("AI-CONFIDENCE SCORE")).toBeInTheDocument()
    expect(screen.getByText("95.0%")).toBeInTheDocument()

    const img = screen.getByAltText("Accident snapshot for log 101")
    expect(img).toBeInTheDocument()
  })

  it("renders confidence score in danger color when confidence is below 75%", () => {
    useAlertStore.setState({
      alerts: [
        {
          ...mockAlert,
          confidence_score: 0.63,
        },
      ],
    })
    render(renderWithProviders(<GlobalAlerts />))

    const scoreEl = screen.getByText("63.0%")
    expect(scoreEl).toBeInTheDocument()
    expect(scoreEl).toHaveClass("text-danger")
  })
})
