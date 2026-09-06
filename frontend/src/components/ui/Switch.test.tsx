import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { Switch } from "./Switch"

describe("Switch", () => {
  it("gives the unchecked thumb a light color visible against the dark track", () => {
    render(<Switch checked={false} label="Enable camera" onChange={vi.fn()} />)

    const track = screen.getByRole("button", { name: "Enable camera" })
    expect(track).toHaveClass("bg-surface-3")
    expect(track.firstElementChild).toHaveClass("bg-fg")
    expect(track.firstElementChild).not.toHaveClass("bg-fg-on-primary")
  })

  it("keeps the checked thumb dark against the light primary track", () => {
    render(<Switch checked label="Enable camera" onChange={vi.fn()} />)

    const track = screen.getByRole("button", { name: "Enable camera" })
    expect(track).toHaveClass("bg-primary")
    expect(track.firstElementChild).toHaveClass("bg-fg-on-primary")
    expect(track.firstElementChild).not.toHaveClass("bg-fg")
  })
})
