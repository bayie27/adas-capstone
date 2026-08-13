import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { StatCard } from "./StatCard"

function DummyIcon() {
  return <svg data-testid="dummy-icon" />
}

describe("StatCard", () => {
  it("renders the title and value", () => {
    render(<StatCard icon={DummyIcon} title="Active Cameras" value={5} />)

    expect(screen.getByText("Active Cameras")).toBeInTheDocument()
    expect(screen.getByText("5")).toBeInTheDocument()
    expect(screen.getByTestId("dummy-icon")).toBeInTheDocument()
  })

  it("omits the delta and subtext when not provided", () => {
    render(<StatCard icon={DummyIcon} title="Active Cameras" value={5} />)

    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })

  it("renders delta with positive styling when deltaPositive is true", () => {
    render(<StatCard icon={DummyIcon} title="Uptime" value="99.9%" delta="+0.4%" deltaPositive />)

    const delta = screen.getByText("+0.4%")
    expect(delta).toHaveClass("text-success")
  })

  it("renders subtext when provided", () => {
    render(<StatCard icon={DummyIcon} title="Alerts" value={2} subtext="Last 24 hours" />)

    expect(screen.getByText("Last 24 hours")).toBeInTheDocument()
  })
})
