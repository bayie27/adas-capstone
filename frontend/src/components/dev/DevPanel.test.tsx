import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { renderWithProviders } from "@/test/wrapper"
import { DevPanelTrigger } from "./DevPanelTrigger"

vi.mock("@/services/dev")

const { getDevStatus } = await import("@/services/dev")

describe("DevPanelTrigger", () => {
  beforeEach(() => {
    vi.mocked(getDevStatus).mockReset()
  })

  it("renders nothing when the probe 404s", async () => {
    // The router is not registered when DEV_TOOLS_ENABLED is false, so the
    // probe fails outright — that is the signal, not a flag in the body.
    vi.mocked(getDevStatus).mockRejectedValue(
      Object.assign(new Error("Not Found"), { response: { status: 404 } }),
    )

    render(renderWithProviders(<DevPanelTrigger />))

    await waitFor(() => expect(getDevStatus).toHaveBeenCalled())
    expect(screen.queryByLabelText("Open dev tools")).not.toBeInTheDocument()
  })

  it("renders the trigger when the backend reports dev tools enabled", async () => {
    vi.mocked(getDevStatus).mockResolvedValue({
      enabled: true,
      profiles: [{ name: "demo", description: "Balanced dataset." }],
    })

    render(renderWithProviders(<DevPanelTrigger />))

    expect(await screen.findByLabelText("Open dev tools")).toBeInTheDocument()
  })

  it("opens the panel with one button per seed profile", async () => {
    const user = (await import("@testing-library/user-event")).default.setup()
    vi.mocked(getDevStatus).mockResolvedValue({
      enabled: true,
      profiles: [
        { name: "demo", description: "Balanced dataset." },
        { name: "empty", description: "Admin only." },
        { name: "perf", description: "100,000 incidents." },
      ],
    })

    render(renderWithProviders(<DevPanelTrigger />))
    await user.click(await screen.findByLabelText("Open dev tools"))

    expect(await screen.findByText("demo")).toBeInTheDocument()
    expect(screen.getByText("empty")).toBeInTheDocument()
    // perf carries a slow marker so nobody clicks it by accident.
    expect(screen.getByText("slow")).toBeInTheDocument()
  })
})
