import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Badge, BadgeDot } from "./Badge"

describe("Badge", () => {
  it("renders a solid neutral pill by default, uppercase and tracked", () => {
    render(<Badge>Resolved</Badge>)
    const badge = screen.getByText("Resolved")
    expect(badge).toHaveClass("bg-surface-3", "uppercase", "rounded-full")
  })

  it("maps each tone onto its semantic token, not a raw colour", () => {
    const { rerender } = render(<Badge tone="success">ok</Badge>)
    expect(screen.getByText("ok")).toHaveClass("bg-success")

    rerender(<Badge tone="warning">ongoing</Badge>)
    expect(screen.getByText("ongoing")).toHaveClass("bg-warning")

    rerender(<Badge tone="danger">down</Badge>)
    expect(screen.getByText("down")).toHaveClass("bg-danger")
  })

  it("uses the subtle triplet for tinted pills", () => {
    render(
      <Badge variant="subtle" tone="success">
        Online
      </Badge>,
    )
    expect(screen.getByText("Online")).toHaveClass("bg-success-subtle", "border-success-border")
  })

  it("can drop the uppercase treatment for numeric deltas", () => {
    render(
      <Badge variant="subtle" tone="success" uppercase={false}>
        +12.5%
      </Badge>,
    )
    expect(screen.getByText("+12.5%")).not.toHaveClass("uppercase")
  })

  it("renders a decorative dot that is hidden from assistive tech", () => {
    const { container } = render(<BadgeDot tone="success" />)
    const dot = container.firstElementChild
    expect(dot).toHaveClass("bg-success", "rounded-full")
    expect(dot).toHaveAttribute("aria-hidden", "true")
  })
})
