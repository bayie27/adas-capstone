import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { SidePanel } from "./SidePanel"

describe("SidePanel", () => {
  it("renders nothing when closed", () => {
    render(
      <SidePanel isOpen={false} onClose={vi.fn()} title="Dev tools">
        <p>body</p>
      </SidePanel>,
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("renders its title and children when open", () => {
    render(
      <SidePanel isOpen onClose={vi.fn()} title="Dev tools" subtitle="Seed data">
        <p>body</p>
      </SidePanel>,
    )
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-label", "Dev tools")
    expect(screen.getByText("Seed data")).toBeInTheDocument()
    expect(screen.getByText("body")).toBeInTheDocument()
  })

  it("closes on Escape", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <SidePanel isOpen onClose={onClose} title="Dev tools">
        <p>body</p>
      </SidePanel>,
    )

    await user.keyboard("{Escape}")
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("closes on a backdrop click", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <SidePanel isOpen onClose={onClose} title="Dev tools">
        <p>body</p>
      </SidePanel>,
    )

    await user.click(screen.getByTestId("side-panel-backdrop"))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("restores body scroll when it unmounts", () => {
    const { unmount } = render(
      <SidePanel isOpen onClose={vi.fn()} title="Dev tools">
        <p>body</p>
      </SidePanel>,
    )
    expect(document.body.style.overflow).toBe("hidden")
    unmount()
    expect(document.body.style.overflow).not.toBe("hidden")
  })
})
