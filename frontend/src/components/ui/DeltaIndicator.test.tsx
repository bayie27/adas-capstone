import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { DeltaIndicator } from "./DeltaIndicator"

describe("DeltaIndicator", () => {
  it("colours a positive tone as success regardless of the value's sign", () => {
    render(<DeltaIndicator value="−5.0%" tone />)
    expect(screen.getByText("−5.0%")).toHaveClass("text-success")
  })

  it("colours a negative tone as danger regardless of the value's sign", () => {
    render(<DeltaIndicator value="+12.5%" tone={false} />)
    expect(screen.getByText("+12.5%")).toHaveClass("text-danger")
  })

  it("colours a null tone as neutral, distinct from success or danger", () => {
    render(<DeltaIndicator value="0%" tone={null} />)
    const el = screen.getByText("0%")
    expect(el).toHaveClass("text-fg-muted")
    expect(el).not.toHaveClass("text-success")
    expect(el).not.toHaveClass("text-danger")
  })

  it("never tints the box itself -- colour lives only on the icon and text", () => {
    render(<DeltaIndicator value="+12.5%" tone />)
    const el = screen.getByText("+12.5%")
    expect(el).toHaveClass("border-stroke", "bg-surface-1")
  })

  it("points the arrow up for a positive value and down for a negative one, independent of tone", () => {
    const { rerender } = render(<DeltaIndicator value="+12.5%" tone={false} />)
    expect(screen.getByTestId("delta-arrow-up")).toBeInTheDocument()

    rerender(<DeltaIndicator value="−5.0%" tone />)
    expect(screen.getByTestId("delta-arrow-down")).toBeInTheDocument()

    rerender(<DeltaIndicator value="0%" tone={null} />)
    expect(screen.getByTestId("delta-arrow-flat")).toBeInTheDocument()
  })
})
