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
    const backdrop = container.querySelector(".bg-backdrop")
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

  /**
   * A snapshot lightbox opened from within an already-open modal nests one
   * overlay inside another. Without stacking, both overlays' Escape handlers
   * would fire on a single keypress and close the modal underneath the
   * lightbox along with the lightbox itself.
   */
  it("closes only the topmost overlay on Escape when two are open", async () => {
    const user = userEvent.setup()
    const onCloseOuter = vi.fn()
    const onCloseInner = vi.fn()
    render(
      <>
        <Modal isOpen onClose={onCloseOuter} title="Outer">
          <p>outer</p>
        </Modal>
        <Modal isOpen onClose={onCloseInner} title="Inner">
          <p>inner</p>
        </Modal>
      </>,
    )

    await user.keyboard("{Escape}")

    expect(onCloseInner).toHaveBeenCalledTimes(1)
    expect(onCloseOuter).not.toHaveBeenCalled()
  })

  it("lets Escape reach the outer overlay once the inner one closes", async () => {
    const user = userEvent.setup()
    const onCloseOuter = vi.fn()
    const onCloseInner = vi.fn()
    const { rerender } = render(
      <>
        <Modal isOpen onClose={onCloseOuter} title="Outer">
          <p>outer</p>
        </Modal>
        <Modal isOpen onClose={onCloseInner} title="Inner">
          <p>inner</p>
        </Modal>
      </>,
    )

    rerender(
      <>
        <Modal isOpen onClose={onCloseOuter} title="Outer">
          <p>outer</p>
        </Modal>
        <Modal isOpen={false} onClose={onCloseInner} title="Inner">
          <p>inner</p>
        </Modal>
      </>,
    )

    await user.keyboard("{Escape}")

    expect(onCloseOuter).toHaveBeenCalledTimes(1)
  })
})
