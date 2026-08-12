import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { Modal } from "./Modal"

/**
 * Modal had no test, and dev_plan/03_PKG_dev_panel.md Step 1 moved its
 * overlay effect into a shared hook. It is used by ConfirmDeleteModal and
 * several pages, so this is the one place a regression from that extraction
 * would otherwise be invisible.
 */
describe("Modal", () => {
  it("renders nothing when closed", () => {
    render(
      <Modal isOpen={false} onClose={vi.fn()} title="Confirm">
        <p>body</p>
      </Modal>,
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("renders its title, subtitle and children when open", () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Confirm" subtitle="Are you sure?">
        <p>body</p>
      </Modal>,
    )
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-label", "Confirm")
    expect(screen.getByText("Are you sure?")).toBeInTheDocument()
    expect(screen.getByText("body")).toBeInTheDocument()
  })

  it("closes on Escape", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <Modal isOpen onClose={onClose} title="Confirm">
        <p>body</p>
      </Modal>,
    )
    await user.keyboard("{Escape}")
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("honours closeOnBackdrop={false}", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const { container } = render(
      <Modal isOpen onClose={onClose} title="Confirm" closeOnBackdrop={false}>
        <p>body</p>
      </Modal>,
    )
    const backdrop = container.querySelector(".bg-black\\/60")
    expect(backdrop).not.toBeNull()
    await user.click(backdrop as Element)
    expect(onClose).not.toHaveBeenCalled()
  })

  it("locks and restores body scroll", () => {
    const { unmount } = render(
      <Modal isOpen onClose={vi.fn()} title="Confirm">
        <p>body</p>
      </Modal>,
    )
    expect(document.body.style.overflow).toBe("hidden")
    unmount()
    expect(document.body.style.overflow).not.toBe("hidden")
  })
})
