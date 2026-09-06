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

  it("renders the delta as a neutral-bordered box, not a tinted pill", () => {
    render(<StatCard icon={DummyIcon} title="Uptime" value="99.9%" delta="+0.4%" deltaPositive />)

    const delta = screen.getByText("+0.4%")
    // The colour lives on the icon/text only; the container itself stays
    // the same neutral border/background regardless of tone.
    expect(delta).toHaveClass("border-stroke", "bg-surface-1")
    expect(delta).not.toHaveClass("bg-success-subtle", "rounded-full")
  })

  it("renders subtext when provided", () => {
    render(<StatCard icon={DummyIcon} title="Alerts" value={2} subtext="Last 24 hours" />)

    expect(screen.getByText("Last 24 hours")).toBeInTheDocument()
  })

  it("renders a negative delta in the danger tone", () => {
    render(<StatCard icon={DummyIcon} title="Uptime" value="98%" delta="-1.2%" />)

    expect(screen.getByText("-1.2%")).toHaveClass("text-danger")
  })

  it("renders a null deltaPositive as the neutral tone, distinct from false", () => {
    render(
      <StatCard
        icon={DummyIcon}
        title="Ongoing Accidents"
        value={4}
        delta="0%"
        deltaPositive={null}
      />,
    )

    const delta = screen.getByText("0%")
    expect(delta).not.toHaveClass("text-danger")
    expect(delta).not.toHaveClass("text-success")
  })

  it("fills the elevated variant with the raised surface", () => {
    const { container } = render(
      <StatCard icon={DummyIcon} title="Total Cameras" value={7} elevated />,
    )

    expect(container.firstElementChild).toHaveClass("bg-surface-2")
  })

  it("shows the ellipsis loading treatment instead of the value", () => {
    render(<StatCard icon={DummyIcon} title="Server Uptime" value={12} isLoading />)

    expect(screen.getByText("…")).toBeInTheDocument()
    expect(screen.queryByText("12")).not.toBeInTheDocument()
  })

  it("renders info icon button when tooltip is provided", () => {
    render(
      <StatCard
        icon={DummyIcon}
        title="Inference Latency"
        value="25ms"
        tooltip="Time to process one frame"
      />,
    )

    const infoButton = screen.getByRole("button", { name: "About Inference Latency" })
    expect(infoButton).toBeInTheDocument()
  })

  it("omits info icon button when tooltip is not provided", () => {
    render(<StatCard icon={DummyIcon} title="Inference Latency" value="25ms" />)

    expect(
      screen.queryByRole("button", { name: "About Inference Latency" }),
    ).not.toBeInTheDocument()
  })
})
