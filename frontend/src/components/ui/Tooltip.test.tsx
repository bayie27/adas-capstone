import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Tooltip } from "./Tooltip"

describe("Tooltip", () => {
  it("does not render tooltip content initially", () => {
    render(
      <Tooltip content="Tooltip explanation text">
        <button type="button">Hover me</button>
      </Tooltip>,
    )

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
    expect(screen.queryByText("Tooltip explanation text")).not.toBeInTheDocument()
  })

  it("shows tooltip content on mouse enter and hides on mouse leave", () => {
    render(
      <Tooltip content="Tooltip explanation text">
        <button type="button">Hover me</button>
      </Tooltip>,
    )

    const trigger = screen.getByRole("button", { name: "Hover me" })
    const wrapper = trigger.parentElement!

    fireEvent.mouseEnter(wrapper)
    expect(screen.getByRole("tooltip")).toBeInTheDocument()
    expect(screen.getByText("Tooltip explanation text")).toBeInTheDocument()

    fireEvent.mouseLeave(wrapper)
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })

  it("shows tooltip on keyboard focus and hides on blur", () => {
    render(
      <Tooltip content="Keyboard accessible tooltip">
        <button type="button">Focus me</button>
      </Tooltip>,
    )

    const trigger = screen.getByRole("button", { name: "Focus me" })
    const wrapper = trigger.parentElement!

    fireEvent.focus(wrapper)
    const tooltip = screen.getByRole("tooltip")
    expect(tooltip).toBeInTheDocument()
    expect(screen.getByText("Keyboard accessible tooltip")).toBeInTheDocument()
    expect(wrapper).toHaveAttribute("aria-describedby", tooltip.id)

    fireEvent.blur(wrapper)
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
    expect(wrapper).not.toHaveAttribute("aria-describedby")
  })

  it("dismisses tooltip on Escape key press", () => {
    render(
      <Tooltip content="Dismiss me with Escape">
        <button type="button">Focus me</button>
      </Tooltip>,
    )

    const trigger = screen.getByRole("button", { name: "Focus me" })
    const wrapper = trigger.parentElement!

    fireEvent.focus(wrapper)
    expect(screen.getByRole("tooltip")).toBeInTheDocument()

    fireEvent.keyDown(wrapper, { key: "Escape" })
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })

  it("keeps tooltip open when focusing interactive content inside it", () => {
    render(
      <Tooltip
        content={
          <div>
            <span>Details</span>
            <button type="button">Learn more</button>
          </div>
        }
      >
        <button type="button">Trigger</button>
      </Tooltip>,
    )

    const trigger = screen.getByRole("button", { name: "Trigger" })
    const wrapper = trigger.parentElement!

    fireEvent.focus(wrapper)
    expect(screen.getByRole("tooltip")).toBeInTheDocument()

    const learnMore = screen.getByRole("button", { name: "Learn more" })
    expect(learnMore).toBeInTheDocument()
  })
})
