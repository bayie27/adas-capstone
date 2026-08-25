import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { FilterSelect } from "./FilterSelect"

describe("FilterSelect", () => {
  const options = [
    { value: "", label: "All actions" },
    { value: "CAMERA_CREATE", label: "Created Camera" },
    { value: "USER_UPDATE", label: "Updated User" },
    { value: "BACKUP_TRIGGER", label: "Triggered Backup" },
  ]

  it("renders dropdown with custom-scrollbar and allows selection", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<FilterSelect value="" options={options} onChange={onChange} />)

    const button = screen.getByRole("button", { name: "All actions" })
    await user.click(button)

    const list = screen.getByRole("list")
    expect(list).toHaveClass("custom-scrollbar")
    expect(screen.getByText("Created Camera")).toBeInTheDocument()

    await user.click(screen.getByText("Triggered Backup"))
    expect(onChange).toHaveBeenCalledWith("BACKUP_TRIGGER")
  })

  it("renders search input when enableSearch is true and filters options", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<FilterSelect value="" options={options} onChange={onChange} enableSearch />)

    const button = screen.getByRole("button", { name: "All actions" })
    await user.click(button)

    const searchInput = screen.getByPlaceholderText("Search...")
    expect(searchInput).toBeInTheDocument()

    await user.type(searchInput, "backup")

    expect(screen.getByText("Triggered Backup")).toBeInTheDocument()
    expect(screen.queryByText("Created Camera")).not.toBeInTheDocument()
    expect(screen.queryByText("Updated User")).not.toBeInTheDocument()

    await user.click(screen.getByText("Triggered Backup"))
    expect(onChange).toHaveBeenCalledWith("BACKUP_TRIGGER")
  })
})
