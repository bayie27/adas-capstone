import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { Sidebar } from "./Sidebar"
import { renderWithProviders } from "@/test/wrapper"
import { useAuthStore } from "@/store/useAuthStore"
import { useAlertStore } from "@/store/useAlertStore"

/**
 * Tracker-bound unit case TC-UNIT-003 (FR-02 Role-Based Access Control).
 *
 * Sidebar.test.tsx already proves an Operator sees no Users, Audit Log or
 * AI Performance destination, and that an Administrator sees all four in the
 * Administration group. The case names Maintenance as a fourth Operator
 * exclusion, which nothing asserted, and requires absence from the rendered
 * output rather than merely being hidden by style.
 */

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  }
})

vi.mock("@/api/auth", () => ({
  logoutUser: vi.fn().mockResolvedValue(undefined),
}))

vi.mock("@/api/users", () => ({
  getMyProfile: vi.fn().mockResolvedValue({
    user_id: 1,
    username: "operator1",
    first_name: "Ops",
    last_name: "User",
    role: "Operator",
    is_active: true,
  }),
  myProfileQueryKey: (userId: number | null) => ["my-profile", userId],
}))

const ADMIN_ONLY = ["Users", "AI Performance", "Audit Log", "Maintenance"]

describe("TC-UNIT-003 role-aware navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAlertStore.setState({
      clockOffsetMs: 0,
      connectionId: "c1234567-89ab-cdef-0123-456789abcdef",
    })
  })

  it("omits every Administrator destination from an Operator's rendered output", () => {
    useAuthStore.setState({ role: "Operator", username: "operator1" })

    render(renderWithProviders(<Sidebar />))

    for (const destination of ADMIN_ONLY) {
      // queryByText asserts absence from the DOM, not a style-hidden node.
      expect(screen.queryByText(destination)).not.toBeInTheDocument()
    }
    // The Operator's own destinations still render, so this is not an
    // empty-render false negative.
    expect(screen.getByText("Dashboard")).toBeInTheDocument()
  })

  it("renders every Administrator destination for an Administrator", () => {
    useAuthStore.setState({ role: "Admin", username: "admin" })

    render(renderWithProviders(<Sidebar />))

    for (const destination of ADMIN_ONLY) {
      expect(screen.getByText(destination)).toBeInTheDocument()
    }
  })
})
