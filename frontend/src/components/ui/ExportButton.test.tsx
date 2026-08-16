import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { ExportButton } from "./ExportButton"

describe("ExportButton", () => {
  it("stays on the static too-large paragraph when onExportJob is not passed", async () => {
    const user = userEvent.setup()
    render(<ExportButton onExport={vi.fn()} rowCount={60_000} />)

    await user.click(screen.getByRole("button", { name: /export/i }))

    expect(screen.getByText(/too large to export directly/i)).toBeInTheDocument()
    expect(screen.queryByText(/run as a background job/i)).not.toBeInTheDocument()
  })

  it("offers the background-job fallback for both formats once both ceilings are exceeded", async () => {
    const user = userEvent.setup()
    const onExportJob = vi.fn()
    render(<ExportButton onExport={vi.fn()} onExportJob={onExportJob} rowCount={60_000} />)

    await user.click(screen.getByRole("button", { name: /export/i }))
    await user.click(screen.getByRole("button", { name: /run as a background job \(csv\)/i }))

    expect(onExportJob).toHaveBeenCalledWith("csv")
  })

  it("does not offer the job fallback when only one ceiling is exceeded", async () => {
    const user = userEvent.setup()
    render(<ExportButton onExport={vi.fn()} onExportJob={vi.fn()} rowCount={15_000} />)

    await user.click(screen.getByRole("button", { name: /export/i }))

    expect(screen.queryByText(/run as a background job/i)).not.toBeInTheDocument()
    expect(screen.getByRole("menuitem", { name: /export as csv/i })).not.toBeDisabled()
    expect(screen.getByRole("menuitem", { name: /export as pdf/i })).toBeDisabled()
  })
})
