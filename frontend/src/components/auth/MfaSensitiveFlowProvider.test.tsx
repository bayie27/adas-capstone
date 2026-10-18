import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { MfaSensitiveFlowProvider } from "./MfaSensitiveFlowProvider"
import { useMfaSensitiveFlow } from "./mfaSensitiveFlow"

function ShowCodes({ onAcknowledged }: { onAcknowledged: () => void }) {
  const flow = useMfaSensitiveFlow()
  return (
    <button
      type="button"
      onClick={() =>
        flow.showCodes({
          codes: ["ABCD-EFGH-JKLM"],
          accountName: "operator",
          onAcknowledged,
        })
      }
    >
      Show one-time codes
    </button>
  )
}

describe("MfaSensitiveFlowProvider", () => {
  it("keeps the code handoff mounted until acknowledgment, then clears and calls once", async () => {
    const user = userEvent.setup()
    const onAcknowledged = vi.fn()
    render(
      <MfaSensitiveFlowProvider>
        <ShowCodes onAcknowledged={onAcknowledged} />
      </MfaSensitiveFlowProvider>,
    )

    await user.click(screen.getByRole("button", { name: /show one-time codes/i }))
    expect(await screen.findByText("ABCD-EFGH-JKLM")).toBeInTheDocument()
    expect(onAcknowledged).not.toHaveBeenCalled()

    await user.click(screen.getByRole("checkbox", { name: /i saved these codes/i }))
    await user.click(screen.getByRole("button", { name: /continue/i }))

    expect(onAcknowledged).toHaveBeenCalledOnce()
    expect(screen.queryByText("ABCD-EFGH-JKLM")).not.toBeInTheDocument()
  })

  it("clears sensitive memory when the provider unmounts", async () => {
    const user = userEvent.setup()
    const onAcknowledged = vi.fn()
    const view = render(
      <MfaSensitiveFlowProvider>
        <ShowCodes onAcknowledged={onAcknowledged} />
      </MfaSensitiveFlowProvider>,
    )

    await user.click(screen.getByRole("button", { name: /show one-time codes/i }))
    expect(await screen.findByText("ABCD-EFGH-JKLM")).toBeInTheDocument()
    view.unmount()

    expect(screen.queryByText("ABCD-EFGH-JKLM")).not.toBeInTheDocument()
    expect(onAcknowledged).not.toHaveBeenCalled()
  })
})
