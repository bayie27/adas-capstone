import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { Button } from "./Button"

describe("Button", () => {
  it("defaults to a non-submitting primary button", () => {
    render(<Button>Add Camera</Button>)
    const button = screen.getByRole("button", { name: "Add Camera" })
    expect(button).toHaveAttribute("type", "button")
    expect(button).toHaveClass("bg-primary")
  })

  it("renders each variant with its own fill", () => {
    const { rerender } = render(<Button variant="secondary">x</Button>)
    expect(screen.getByRole("button")).toHaveClass("bg-surface-3")

    rerender(<Button variant="outline">x</Button>)
    expect(screen.getByRole("button")).toHaveClass("border-border")

    rerender(<Button variant="destructive">x</Button>)
    expect(screen.getByRole("button")).toHaveClass("bg-danger")
  })

  it("swaps the label and disables itself while loading", () => {
    render(
      <Button isLoading loadingLabel="Signing in…">
        Login
      </Button>,
    )
    const button = screen.getByRole("button")
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute("aria-busy", "true")
    expect(button).toHaveTextContent("Signing in…")
    expect(button).not.toHaveTextContent("Login")
  })

  it("does not fire onClick while loading or disabled", async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()

    const { rerender } = render(
      <Button isLoading loadingLabel="Deleting…" onClick={onClick}>
        Delete
      </Button>,
    )
    await user.click(screen.getByRole("button"))
    expect(onClick).not.toHaveBeenCalled()

    rerender(
      <Button disabled onClick={onClick}>
        Delete
      </Button>,
    )
    await user.click(screen.getByRole("button"))
    expect(onClick).not.toHaveBeenCalled()
  })

  it("carries the shared focus-visible ring and disabled treatment", () => {
    render(<Button>x</Button>)
    const button = screen.getByRole("button")
    expect(button).toHaveClass("focus-visible:outline-stroke-strong")
    expect(button).toHaveClass("disabled:opacity-60")
  })

  it("is reachable and activatable from the keyboard", async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Confirm</Button>)

    await user.tab()
    expect(screen.getByRole("button")).toHaveFocus()
    await user.keyboard("{Enter}")
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})
