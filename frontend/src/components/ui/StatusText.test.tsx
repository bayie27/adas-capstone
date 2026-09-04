import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AlertStatusText, CameraAiText, CameraConnectionText } from "./StatusText"
import { getAlertStatusTone, getCameraAiTone, getCameraConnectionTone } from "./statusTone"

// A reversed mapping here makes a broken camera read as healthy, so every
// status in each union is asserted rather than a representative sample.
describe("status tone mapping", () => {
  it("maps every camera connection status", () => {
    expect(getCameraConnectionTone("Connected")).toBe("success")
    expect(getCameraConnectionTone("Reconnecting")).toBe("warning")
    expect(getCameraConnectionTone("Disconnected")).toBe("danger")
    expect(getCameraConnectionTone("Unresponsive")).toBe("danger")
  })

  it("maps every camera AI status", () => {
    expect(getCameraAiTone("Active")).toBe("success")
    expect(getCameraAiTone("Paused")).toBe("warning")
    expect(getCameraAiTone("Inactive")).toBe("danger")
    expect(getCameraAiTone("Unresponsive")).toBe("danger")
  })

  it("maps every alert status", () => {
    expect(getAlertStatusTone("Ongoing")).toBe("warning")
    expect(getAlertStatusTone("Cleared")).toBe("success")
    expect(getAlertStatusTone("Dismissed")).toBe("neutral")
    expect(getAlertStatusTone("Unverified")).toBe("default")
  })

  it("never renders a healthy colour for a failed camera", () => {
    render(<CameraConnectionText status="Disconnected" />)
    const el = screen.getByText("Disconnected")
    expect(el).toHaveClass("text-danger")
    expect(el).not.toHaveClass("text-success")
  })

  it("renders the tone class for each domain wrapper", () => {
    const { rerender } = render(<CameraAiText status="Paused" />)
    expect(screen.getByText("Paused")).toHaveClass("text-warning")

    rerender(<AlertStatusText status="Cleared" />)
    expect(screen.getByText("Cleared")).toHaveClass("text-success")
  })
})
