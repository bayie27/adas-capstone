import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

import { Sidebar } from "./Sidebar"
import { useAuthStore } from "@/store/useAuthStore"
import { useAlertStore } from "@/store/useAlertStore"
import * as authApi from "@/api/auth"

const mockNavigate = vi.fn()

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock("@/api/auth", () => ({
  logoutUser: vi.fn().mockResolvedValue(undefined),
}))

describe("Sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      role: "Admin",
      username: "olivia.quinn",
    })
    useAlertStore.setState({
      clockOffsetMs: 0,
      connectionId: "c1234567-89ab-cdef-0123-456789abcdef",
    })
  })

  it("renders user information and inline logout button with hover styling", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    )

    expect(screen.getByText("olivia.quinn")).toBeInTheDocument()
    expect(screen.getByText("Administrator")).toBeInTheDocument()

    const logoutButton = screen.getByRole("button", { name: "Log Out" })
    expect(logoutButton).toBeInTheDocument()
    expect(logoutButton).toHaveClass("hover:text-danger")
    expect(logoutButton).toHaveClass("hover:bg-danger-subtle")
  })

  it("calls logoutUser, clears session, and navigates to /login when clicked", async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    )

    const logoutButton = screen.getByRole("button", { name: "Log Out" })
    await user.click(logoutButton)

    expect(authApi.logoutUser).toHaveBeenCalled()
    expect(useAuthStore.getState().username).toBeNull()
    expect(mockNavigate).toHaveBeenCalledWith("/login", { replace: true })
  })

  it("renders navigation items according to user role", () => {
    useAuthStore.setState({ role: "Operator" })

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    )

    expect(screen.getByText("Dashboard")).toBeInTheDocument()
    expect(screen.getByText("Cameras")).toBeInTheDocument()
    expect(screen.getByText("Detections")).toBeInTheDocument()
    expect(screen.queryByText("Users")).not.toBeInTheDocument()
    expect(screen.queryByText("Audit Log")).not.toBeInTheDocument()
  })

  it("displays clock skew warning when clockOffsetMs exceeds threshold", () => {
    useAlertStore.setState({ clockOffsetMs: 75_000 })

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    )

    expect(screen.getByRole("status")).toHaveTextContent("This device's clock is off by")
  })
})
