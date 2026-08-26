import { render, screen, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ToastContainer } from "@/components/ui/ToastContainer"
import { toast, useToastStore } from "@/store/useToastStore"

describe("ToastContainer & useToastStore", () => {
  beforeEach(() => {
    act(() => {
      useToastStore.getState().clearAll()
    })
    vi.useFakeTimers()
  })

  it("renders nothing when there are no toasts", () => {
    const { container } = render(<ToastContainer />)
    expect(container.firstChild).toBeNull()
  })

  it("renders toast when toast.success is called and displays its message and tone", () => {
    render(<ToastContainer />)

    act(() => {
      toast.success("Camera added successfully.", { title: "Success" })
    })

    expect(screen.getByText("Camera added successfully.")).toBeInTheDocument()
    expect(screen.getByText("Success")).toBeInTheDocument()
  })

  it("renders error, warning, and info toasts", () => {
    render(<ToastContainer />)

    act(() => {
      toast.error("Failed to connect.")
      toast.warning("Low battery detected.")
      toast.info("Export started.")
    })

    expect(screen.getByText("Failed to connect.")).toBeInTheDocument()
    expect(screen.getByText("Low battery detected.")).toBeInTheDocument()
    expect(screen.getByText("Export started.")).toBeInTheDocument()
  })

  it("dismisses a toast when the close button is clicked", async () => {
    vi.useRealTimers()
    const user = userEvent.setup()
    render(<ToastContainer />)

    act(() => {
      toast.success("User created.")
    })

    expect(screen.getByText("User created.")).toBeInTheDocument()
    const closeBtn = screen.getByRole("button", { name: "Dismiss notification" })
    await user.click(closeBtn)

    expect(screen.queryByText("User created.")).not.toBeInTheDocument()
  })

  it("auto-dismisses a toast after specified duration", () => {
    render(<ToastContainer />)

    act(() => {
      toast.success("Temporary notification", { duration: 3000 })
    })

    expect(screen.getByText("Temporary notification")).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    expect(screen.queryByText("Temporary notification")).not.toBeInTheDocument()
  })
})
