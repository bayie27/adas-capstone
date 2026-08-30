import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { renderWithProviders } from "@/test/wrapper"
import { DevPanelTrigger } from "./DevPanelTrigger"

vi.mock("@/api/dev")

const { getDevStatus, reseedProfile } = await import("@/api/dev")

describe("DevPanelTrigger", () => {
  beforeEach(() => {
    vi.mocked(getDevStatus).mockReset()
    vi.mocked(reseedProfile).mockReset()
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

  it("shows the targeted UAT preparation controls when uat is registered", async () => {
    const user = (await import("@testing-library/user-event")).default.setup()
    vi.mocked(getDevStatus).mockResolvedValue({
      enabled: true,
      profiles: [{ name: "uat", description: "Frozen UAT baseline." }],
    })

    render(renderWithProviders(<DevPanelTrigger />))
    await user.click(await screen.findByLabelText("Open dev tools"))

    expect(await screen.findByText("Prepare next Operator")).toBeInTheDocument()
    expect(screen.getByText("Prepare next Administrator")).toBeInTheDocument()
    expect(screen.getByText("Restore AD-J02 healthy baseline")).toBeInTheDocument()
  })

  it("requires an explicit named confirmation before any destructive reseed", async () => {
    const user = (await import("@testing-library/user-event")).default.setup()
    vi.mocked(getDevStatus).mockResolvedValue({
      enabled: true,
      profiles: [{ name: "analytics", description: "Analytics profile." }],
    })
    vi.mocked(reseedProfile).mockResolvedValue({
      profile: "analytics",
      users: 8,
      cameras: 8,
      detections: 62,
      health_samples: 9363,
      export_jobs: 5,
      snapshots: 62,
      audit_rows: 0,
      session: { user_id: 1, username: "admin", role: "Admin" },
    })

    render(renderWithProviders(<DevPanelTrigger />))
    await user.click(await screen.findByLabelText("Open dev tools"))
    await user.click((await screen.findByText("analytics")).closest("button") as HTMLElement)

    expect(reseedProfile).not.toHaveBeenCalled()
    expect(
      screen.getByText(/permanently replaces the development database and active sessions/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Confirm reseed 'analytics'" }))

    await waitFor(() => expect(reseedProfile).toHaveBeenCalledWith("analytics"))
    expect(reseedProfile).toHaveBeenCalledTimes(1)
  })

  it("cancels a pending reseed without calling the API", async () => {
    const user = (await import("@testing-library/user-event")).default.setup()
    vi.mocked(getDevStatus).mockResolvedValue({
      enabled: true,
      profiles: [{ name: "uat", description: "Frozen UAT baseline." }],
    })

    render(renderWithProviders(<DevPanelTrigger />))
    await user.click(await screen.findByLabelText("Open dev tools"))
    await user.click((await screen.findByText("uat")).closest("button") as HTMLElement)
    await user.click(screen.getByRole("button", { name: "Cancel reseed" }))

    expect(reseedProfile).not.toHaveBeenCalled()
    expect(screen.queryByRole("button", { name: "Confirm reseed 'uat'" })).not.toBeInTheDocument()
  })
})
