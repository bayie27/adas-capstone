import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { PaginationFooter } from "./PaginationFooter"

describe("PaginationFooter", () => {
  it("renders footer when totalFiltered <= pageSize so items per page and count stay accessible", () => {
    render(
      <PaginationFooter
        page={1}
        totalPages={1}
        rangeStart={1}
        rangeEnd={15}
        totalFiltered={15}
        pageSize={25}
        isFetching={false}
        onPrev={vi.fn()}
        onNext={vi.fn()}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
      />,
    )

    expect(screen.getByText("1-15 of 15")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Items per page" })).toHaveTextContent("25")
    expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled()
  })

  it("returns null when totalFiltered is 0", () => {
    const { container } = render(
      <PaginationFooter
        page={1}
        totalPages={1}
        rangeStart={0}
        rangeEnd={0}
        totalFiltered={0}
        pageSize={10}
        isFetching={false}
        onPrev={vi.fn()}
        onNext={vi.fn()}
      />,
    )

    expect(container.firstChild).toBeNull()
  })

  it("calls onPageSizeChange when selecting a new page size from the dropdown", async () => {
    const user = userEvent.setup()
    const onPageSizeChange = vi.fn()

    render(
      <PaginationFooter
        page={1}
        totalPages={2}
        rangeStart={1}
        rangeEnd={10}
        totalFiltered={15}
        pageSize={10}
        isFetching={false}
        onPrev={vi.fn()}
        onNext={vi.fn()}
        onPageSizeChange={onPageSizeChange}
      />,
    )

    const dropdownButton = screen.getByRole("button", { name: "Items per page" })
    await user.click(dropdownButton)

    const option25 = screen.getByText("25")
    await user.click(option25)

    expect(onPageSizeChange).toHaveBeenCalledWith(25)
  })
})
