import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { CameraBreakdownBar } from "./CameraBreakdownBar"
import type { CameraBreakdowns } from "@/api/cameras"

const BREAKDOWNS: CameraBreakdowns = {
  connection: { connected: 4, disconnected: 1, reconnecting: 0, unresponsive: 2 },
  ai: { active: 3, paused: 1, inactive: 1, unresponsive: 5 },
}

describe("CameraBreakdownBar", () => {
  it("renders nothing when breakdowns hasn't loaded yet", () => {
    render(
      <CameraBreakdownBar
        breakdowns={undefined}
        activeConnectionStatus={null}
        activeAiStatus={null}
        onSelectConnectionStatus={vi.fn()}
        onSelectAiStatus={vi.fn()}
      />,
    )
    expect(screen.queryByText("Connected")).not.toBeInTheDocument()
  })

  it("reports the clicked status without deciding toggle/replace itself", async () => {
    const user = userEvent.setup()
    const onSelectConnectionStatus = vi.fn()
    render(
      <CameraBreakdownBar
        breakdowns={BREAKDOWNS}
        activeConnectionStatus={null}
        activeAiStatus={null}
        onSelectConnectionStatus={onSelectConnectionStatus}
        onSelectAiStatus={vi.fn()}
      />,
    )

    await user.click(screen.getByRole("button", { name: /unresponsive.*2/i }))
    expect(onSelectConnectionStatus).toHaveBeenCalledWith("Unresponsive")
  })

  it("renders the active status as pressed and others as not", () => {
    render(
      <CameraBreakdownBar
        breakdowns={BREAKDOWNS}
        activeConnectionStatus="Connected"
        activeAiStatus={null}
        onSelectConnectionStatus={vi.fn()}
        onSelectAiStatus={vi.fn()}
      />,
    )

    expect(screen.getByRole("button", { name: /^connected.*4/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    expect(screen.getByRole("button", { name: /disconnected.*1/i })).toHaveAttribute(
      "aria-pressed",
      "false",
    )
  })
})
