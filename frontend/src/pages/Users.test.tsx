import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import Users from "./Users"
import type { UserRecord } from "@/api/users"

vi.mock("@/api/users", async () => {
  const actual = await vi.importActual<typeof import("@/api/users")>("@/api/users")
  return {
    ...actual,
    getUsers: vi.fn(),
    restoreUser: vi.fn(),
    deleteUser: vi.fn(),
  }
})

import { getUsers, restoreUser } from "@/api/users"

const mockActiveUser: UserRecord = {
  user_id: 1,
  username: "admin.active",
  first_name: "Alice",
  last_name: "Smith",
  role: "Admin",
  is_active: true,
  created_at: "2026-08-01T12:00:00Z",
  updated_at: "2026-08-01T12:00:00Z",
  password_changed_at: null,
  last_login: null,
}

const mockDeactivatedUser: UserRecord = {
  user_id: 2,
  username: "bbutterbonia",
  first_name: "Bob",
  last_name: "Butter",
  role: "Operator",
  is_active: false,
  created_at: "2026-08-01T12:00:00Z",
  updated_at: "2026-08-01T12:00:00Z",
  password_changed_at: null,
  last_login: null,
}

function renderUsers() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Users />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("Users Page Actions", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders edit, reset password, and delete buttons for active users", async () => {
    vi.mocked(getUsers).mockResolvedValue({
      total_filtered: 1,
      users: [mockActiveUser],
    })

    renderUsers()

    expect(await screen.findByText("Alice Smith")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Edit Alice Smith" })).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Reset password for Alice Smith" }),
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Delete Alice Smith" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Restore Alice Smith" })).not.toBeInTheDocument()
  })

  it("renders restore button for deactivated users instead of active actions", async () => {
    vi.mocked(getUsers).mockResolvedValue({
      total_filtered: 1,
      users: [mockDeactivatedUser],
    })

    renderUsers()

    expect(await screen.findByText("Bob Butter")).toBeInTheDocument()
    expect(screen.getByText("Deactivated")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Restore Bob Butter" })).toBeInTheDocument()

    expect(screen.queryByRole("button", { name: "Edit Bob Butter" })).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Reset password for Bob Butter" }),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Delete Bob Butter" })).not.toBeInTheDocument()
  })

  it("triggers restoreUser mutation when restore button is clicked", async () => {
    const user = userEvent.setup()
    vi.mocked(getUsers).mockResolvedValue({
      total_filtered: 1,
      users: [mockDeactivatedUser],
    })
    vi.mocked(restoreUser).mockResolvedValue({
      ...mockDeactivatedUser,
      is_active: true,
    })

    renderUsers()

    const restoreButton = await screen.findByRole("button", { name: "Restore Bob Butter" })
    await user.click(restoreButton)

    expect(restoreUser).toHaveBeenCalledWith(2)
    expect(await screen.findByText("bbutterbonia was restored.")).toBeInTheDocument()
  })
})
