import { useState } from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

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

describe("DateRangePicker", () => {
  it("commits native input events to its controlled parent state", () => {
    render(<ControlledDateRangePicker />)

    fireEvent.input(screen.getByLabelText("Incident date range start"), {
      target: { value: "2026-08-16" },
    })
    fireEvent.input(screen.getByLabelText("Incident date range end"), {
      target: { value: "2026-08-30" },
    })

    expect(screen.getByRole("status")).toHaveTextContent("2026-08-16|2026-08-30")
  })
})
