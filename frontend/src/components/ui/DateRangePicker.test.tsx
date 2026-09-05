import { useState } from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { DateRangePicker } from "./DateRangePicker"

function ControlledDateRangePicker() {
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")

  return (
    <>
      <DateRangePicker
        start={start}
        end={end}
        onStartChange={setStart}
        onEndChange={setEnd}
        label="Incident date range"
      />
      <output>{`${start}|${end}`}</output>
    </>
  )
}

function setup() {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  // Noon in Manila on 2026-09-05, well clear of any day boundary.
  vi.setSystemTime(new Date("2026-09-05T04:00:00Z"))
  const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
  render(<ControlledDateRangePicker />)
  return user
}

const trigger = () => screen.getByRole("button", { name: "Incident date range" })

describe("DateRangePicker", () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it("shows a neutral placeholder before any range is committed", () => {
    setup()
    expect(trigger()).toHaveTextContent("Select date range")
  })

  it("commits a preset range in a single click", async () => {
    const user = setup()

    await user.click(trigger())
    await user.click(screen.getByRole("button", { name: "Last 7 days" }))

    expect(screen.getByRole("status")).toHaveTextContent("2026-08-30|2026-09-05")
    expect(trigger()).toHaveTextContent("Last 7 days")
  })

  it("commits Today as a single-day range", async () => {
    const user = setup()

    await user.click(trigger())
    await user.click(screen.getByRole("button", { name: "Today" }))

    expect(screen.getByRole("status")).toHaveTextContent("2026-09-05|2026-09-05")
  })

  it("orders a custom range regardless of which day is clicked first", async () => {
    const user = setup()

    await user.click(trigger())
    await user.click(screen.getByRole("button", { name: "Custom range" }))
    await user.click(screen.getByRole("button", { name: "September 12, 2026" }))
    await user.click(screen.getByRole("button", { name: "September 5, 2026" }))
    await user.click(screen.getByRole("button", { name: "Apply" }))

    expect(screen.getByRole("status")).toHaveTextContent("2026-09-05|2026-09-12")
  })

  it("does not commit a custom pick until Apply is clicked", async () => {
    const user = setup()

    await user.click(trigger())
    await user.click(screen.getByRole("button", { name: "Custom range" }))
    await user.click(screen.getByRole("button", { name: "September 5, 2026" }))

    expect(screen.getByRole("status")).toHaveTextContent("|")
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled()
  })

  it("discards a pending custom pick on Cancel", async () => {
    const user = setup()

    await user.click(trigger())
    await user.click(screen.getByRole("button", { name: "Custom range" }))
    await user.click(screen.getByRole("button", { name: "September 5, 2026" }))
    await user.click(screen.getByRole("button", { name: "September 12, 2026" }))
    await user.click(screen.getByRole("button", { name: "Cancel" }))

    expect(screen.getByRole("status")).toHaveTextContent("|")
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument()
  })

  it("discards a pending custom pick on Escape", async () => {
    const user = setup()

    await user.click(trigger())
    await user.click(screen.getByRole("button", { name: "Custom range" }))
    await user.click(screen.getByRole("button", { name: "September 5, 2026" }))
    await user.keyboard("{Escape}")

    expect(screen.getByRole("status")).toHaveTextContent("|")
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument()
  })

  it("re-opens showing the currently committed preset as selected", async () => {
    const user = setup()

    await user.click(trigger())
    await user.click(screen.getByRole("button", { name: "Today" }))
    await user.click(trigger())

    expect(screen.getByRole("button", { name: "Today" })).toHaveClass("bg-surface-3")
  })

  it("disables the trigger and never opens the popover", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date("2026-09-05T04:00:00Z"))
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
    render(
      <DateRangePicker start="" end="" onStartChange={vi.fn()} onEndChange={vi.fn()} disabled />,
    )

    await user.click(screen.getByRole("button", { name: "Date range" }))

    expect(screen.queryByRole("button", { name: "Custom range" })).not.toBeInTheDocument()
  })
})
