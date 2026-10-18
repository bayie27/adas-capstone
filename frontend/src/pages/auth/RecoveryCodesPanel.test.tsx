import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { RecoveryCodesPanel } from "./RecoveryCodesPanel"

const codes = ["ABCD-EFGH-JKLM", "NPQR-STUV-WXYZ"]
const originalCreateObjectURL = Object.getOwnPropertyDescriptor(URL, "createObjectURL")
const originalRevokeObjectURL = Object.getOwnPropertyDescriptor(URL, "revokeObjectURL")

function restoreUrlMethod(
  name: "createObjectURL" | "revokeObjectURL",
  descriptor?: PropertyDescriptor,
) {
  if (descriptor) Object.defineProperty(URL, name, descriptor)
  else Reflect.deleteProperty(URL, name)
}

function setClipboard(writeText: ReturnType<typeof vi.fn>) {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  })
}

describe("RecoveryCodesPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined })
    restoreUrlMethod("createObjectURL", originalCreateObjectURL)
    restoreUrlMethod("revokeObjectURL", originalRevokeObjectURL)
  })

  it("requires an explicit acknowledgment before continuing and calls it once", async () => {
    const user = userEvent.setup()
    const onAcknowledged = vi.fn()
    render(
      <RecoveryCodesPanel codes={codes} accountName="operator" onAcknowledged={onAcknowledged} />,
    )

    const continueButton = screen.getByRole("button", { name: /continue/i })
    expect(continueButton).toBeDisabled()
    expect(onAcknowledged).not.toHaveBeenCalled()

    await user.click(screen.getByRole("checkbox", { name: /i saved these codes/i }))
    expect(continueButton).toBeEnabled()
    await user.click(continueButton)
    await user.click(continueButton)

    expect(onAcknowledged).toHaveBeenCalledOnce()
  })

  it("copies only after an explicit click and leaves codes visible when clipboard fails", async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockRejectedValue(new Error("clipboard unavailable"))
    setClipboard(writeText)
    const onAcknowledged = vi.fn()

    render(
      <RecoveryCodesPanel codes={codes} accountName="operator" onAcknowledged={onAcknowledged} />,
    )
    expect(writeText).not.toHaveBeenCalled()
    await user.click(screen.getByRole("button", { name: /copy codes/i }))

    expect(writeText).toHaveBeenCalledWith(codes.join("\n"))
    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn.t copy/i)
    expect(screen.getByText(codes[0])).toBeInTheDocument()
    expect(onAcknowledged).not.toHaveBeenCalled()
  })

  it("downloads through a local Blob and revokes the temporary object URL", async () => {
    const user = userEvent.setup()
    const createObjectURL = vi.fn().mockReturnValue("blob:local-recovery-codes")
    const revokeObjectURL = vi.fn()
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})

    render(<RecoveryCodesPanel codes={codes} accountName="operator" onAcknowledged={vi.fn()} />)
    expect(createObjectURL).not.toHaveBeenCalled()
    await user.click(screen.getByRole("button", { name: /download .txt/i }))

    expect(createObjectURL).toHaveBeenCalledOnce()
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:local-recovery-codes")
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled()
  })

  it("reports download failure inline without hiding or acknowledging the batch", async () => {
    const user = userEvent.setup()
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => {
        throw new Error("download unavailable")
      }),
    })
    const onAcknowledged = vi.fn()

    render(
      <RecoveryCodesPanel codes={codes} accountName="operator" onAcknowledged={onAcknowledged} />,
    )
    await user.click(screen.getByRole("button", { name: /download .txt/i }))

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn.t download/i)
    expect(screen.getByText(codes[0])).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled()
    expect(onAcknowledged).not.toHaveBeenCalled()
  })
})
