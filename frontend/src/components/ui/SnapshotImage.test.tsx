import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { SnapshotImage } from "./SnapshotImage"

describe("SnapshotImage", () => {
  it("renders the fallback when there is no snapshot URL", () => {
    render(<SnapshotImage snapshotUrl={null} alt="Accident snapshot" />)
    expect(screen.getByText("Snapshot unavailable")).toBeInTheDocument()
  })

  it("renders a plain, non-interactive image when not zoomable", () => {
    render(<SnapshotImage snapshotUrl="/api/alerts/1/snapshot" alt="Accident snapshot" />)
    expect(screen.getByRole("img", { name: "Accident snapshot" })).toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })

  it("opens and closes the zoom lightbox when zoomable", async () => {
    const user = userEvent.setup()
    render(<SnapshotImage snapshotUrl="/api/alerts/1/snapshot" alt="Accident snapshot" zoomable />)

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Zoom in on Accident snapshot" }))
    expect(screen.getByRole("dialog", { name: "Accident snapshot" })).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Close zoomed snapshot" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("closes the lightbox if the snapshot URL changes while zoomed", async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <SnapshotImage snapshotUrl="/api/alerts/1/snapshot" alt="Accident 1 snapshot" zoomable />,
    )

    await user.click(screen.getByRole("button", { name: "Zoom in on Accident 1 snapshot" }))
    expect(screen.getByRole("dialog")).toBeInTheDocument()

    // Simulates paging to a different accident in GlobalAlerts' queue
    // without the SnapshotImage instance unmounting.
    rerender(
      <SnapshotImage snapshotUrl="/api/alerts/2/snapshot" alt="Accident 2 snapshot" zoomable />,
    )

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })
})
