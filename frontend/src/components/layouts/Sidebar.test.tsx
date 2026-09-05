import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { Sidebar } from "./Sidebar"
import { renderWithProviders } from "@/test/wrapper"
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

vi.mock("@/api/users", () => ({
  getMyProfile: vi.fn().mockResolvedValue({
    user_id: 1,
    username: "admin",
    first_name: "System",
    last_name: "Administrator",
    role: "Admin",
    is_active: true,
  }),
  myProfileQueryKey: (userId: number | null) => ["my-profile", userId],
}))

describe("Sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      role: "Admin",
      username: "admin",
    })
    useAlertStore.setState({
      clockOffsetMs: 0,
      connectionId: "c1234567-89ab-cdef-0123-456789abcdef",
    })
  })

  it("renders user information and initials matching profile data", async () => {
    render(renderWithProviders(<Sidebar />))

    expect(await screen.findByText("System Administrator")).toBeInTheDocument()
    expect(screen.getByText("SA")).toBeInTheDocument()
    expect(screen.getByText("Administrator")).toBeInTheDocument()

    const logoutButton = screen.getByRole("button", { name: "Log Out" })
    expect(logoutButton).toBeInTheDocument()
    expect(logoutButton).toHaveClass("hover:text-danger")
    expect(logoutButton).toHaveClass("hover:bg-danger-subtle")
  })

  it("calls logoutUser, clears session, and navigates to /login when clicked", async () => {
    const user = userEvent.setup()

    render(renderWithProviders(<Sidebar />))

    const logoutButton = screen.getByRole("button", { name: "Log Out" })
    await user.click(logoutButton)

    expect(authApi.logoutUser).toHaveBeenCalled()
    expect(useAuthStore.getState().username).toBeNull()
    expect(mockNavigate).toHaveBeenCalledWith("/login", { replace: true })
  })

  it("renders navigation items according to user role", () => {
    useAuthStore.setState({ role: "Operator" })

    render(renderWithProviders(<Sidebar />))

    expect(screen.getByText("Dashboard")).toBeInTheDocument()
    expect(screen.getByText("Cameras")).toBeInTheDocument()
    expect(screen.getByText("Detections")).toBeInTheDocument()
    expect(screen.queryByText("Users")).not.toBeInTheDocument()
    expect(screen.queryByText("Audit Log")).not.toBeInTheDocument()
    expect(screen.queryByText("AI Performance")).not.toBeInTheDocument()
  })

  it("places AI Performance last in the Administrator group", () => {
    render(renderWithProviders(<Sidebar />))

    const administration = screen.getByRole("heading", { name: "ADMINISTRATION" }).parentElement
    expect(administration).not.toBeNull()
    expect(
      within(administration!)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Users", "Audit Log", "Maintenance", "AI Performance"])
  })

  it("displays clock skew warning when clockOffsetMs exceeds threshold", () => {
    useAlertStore.setState({ clockOffsetMs: 75_000 })

    render(renderWithProviders(<Sidebar />))

    expect(screen.getByRole("status")).toHaveTextContent("This device's clock is off by")
  })
})
