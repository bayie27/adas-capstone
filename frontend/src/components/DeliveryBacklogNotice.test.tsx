import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { DeliveryBacklogNotice } from "./DeliveryBacklogNotice"

describe("DeliveryBacklogNotice", () => {
  it("renders nothing when there is no pending backlog", () => {
    render(
      <DeliveryBacklogNotice
        pendingCount={0}
        oldestPendingAgeSeconds={null}
        quarantinedCount={0}
      />,
    )
    expect(screen.queryByRole("status")).not.toBeInTheDocument()
  })

  it("renders a warning-toned notice for a pending-only backlog", () => {
    render(
      <DeliveryBacklogNotice pendingCount={3} oldestPendingAgeSeconds={90} quarantinedCount={0} />,
    )
    const notice = screen.getByRole("status")
    expect(notice).toHaveTextContent("3 accident detections awaiting delivery to the backend")
    expect(notice).toHaveTextContent("oldest: 1 minute")
    expect(notice.firstElementChild).toHaveClass("text-warning")
    expect(notice).not.toHaveTextContent("quarantined")
  })

  it("escalates to danger tone and names the quarantined count when non-zero", () => {
    render(
      <DeliveryBacklogNotice pendingCount={5} oldestPendingAgeSeconds={600} quarantinedCount={2} />,
    )
    const notice = screen.getByRole("status")
    expect(notice.firstElementChild).toHaveClass("text-danger")
    expect(notice).toHaveTextContent("2 quarantined and will not be retried.")
  })

  it("singularizes a single pending detection", () => {
    render(
      <DeliveryBacklogNotice
        pendingCount={1}
        oldestPendingAgeSeconds={null}
        quarantinedCount={0}
      />,
    )
    expect(screen.getByRole("status")).toHaveTextContent(
      "1 accident detection awaiting delivery to the backend.",
    )
  })
})
