import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { Table, TableHead, TableHeaderCell } from "@/components/ui/Table"

/**
 * The sortable header's correctness is mostly invisible: `aria-sort` is the
 * only signal a screen-reader user gets that a column is sortable at all,
 * because D-8(a) deliberately withholds the visual affordance until hover.
 * A wrong value there is silent for everyone who can see the chevron.
 */
function renderHeader(props: Parameters<typeof TableHeaderCell>[0]) {
  return render(
    <Table>
      <TableHead>
        <TableHeaderCell {...props} />
      </TableHead>
    </Table>,
  )
}

describe("TableHeaderCell", () => {
  it("renders a plain th with no aria-sort when not sortable", () => {
    renderHeader({ children: "Camera Name" })

    const header = screen.getByRole("columnheader", { name: "Camera Name" })
    expect(header).not.toHaveAttribute("aria-sort")
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("marks a sortable but inactive column aria-sort=none", () => {
    renderHeader({
      children: "Confidence",
      sort: { key: "confidence_score", active: null, onSort: vi.fn() },
    })

    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "none")
  })

  it.each([
    ["asc", "ascending"],
    ["desc", "descending"],
  ] as const)("maps active=%s to aria-sort=%s", (active, expected) => {
    renderHeader({
      children: "Confidence",
      sort: { key: "confidence_score", active, onSort: vi.fn() },
    })

    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", expected)
  })

  it("calls onSort with the allowlisted key, not the label", async () => {
    const onSort = vi.fn()
    renderHeader({
      children: "AI Confidence Score",
      sort: { key: "confidence_score", active: null, onSort },
    })

    await userEvent.click(screen.getByRole("button"))

    expect(onSort).toHaveBeenCalledExactlyOnceWith("confidence_score")
  })
})
