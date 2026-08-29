import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { HealthMetricsReferenceModal } from "./HealthMetricsReferenceModal"

describe("HealthMetricsReferenceModal", () => {
  it("does not render dialog content when isOpen is false", () => {
    render(<HealthMetricsReferenceModal isOpen={false} onClose={vi.fn()} />)

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.queryByText("Performance Metrics Reference")).not.toBeInTheDocument()
  })

  it("renders metric reference tables when open", () => {
    render(<HealthMetricsReferenceModal isOpen={true} onClose={vi.fn()} />)

    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.getByText("Performance Metrics Reference")).toBeInTheDocument()

    // AI Processing Time section & ranges
    expect(screen.getByText("AI Processing Time")).toBeInTheDocument()
    expect(screen.getByText("15–45ms")).toBeInTheDocument()
    expect(screen.getByText("45–70ms")).toBeInTheDocument()
    expect(
      screen.getByText("Fast enough for real-time processing without queuing or frame drops"),
    ).toBeInTheDocument()

    // Processing Speed section & ranges
    expect(screen.getByText("Processing Speed")).toBeInTheDocument()
    expect(screen.getByText("10.0–15.0 fps")).toBeInTheDocument()
    expect(screen.getByText("Below 10.0 fps")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Matches the system's calibrated target band for accurate accident detection",
      ),
    ).toBeInTheDocument()
  })

  it("calls onClose when close button is clicked", () => {
    const onClose = vi.fn()
    render(<HealthMetricsReferenceModal isOpen={true} onClose={onClose} />)

    const closeBtn = screen.getByRole("button", { name: "Close dialog" })
    fireEvent.click(closeBtn)

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("calls onClose when Escape key is pressed", () => {
    const onClose = vi.fn()
    render(<HealthMetricsReferenceModal isOpen={true} onClose={onClose} />)

    fireEvent.keyDown(document, { key: "Escape" })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
