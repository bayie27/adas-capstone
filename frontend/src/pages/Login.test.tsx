import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, useLocation } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import type { CurrentUserResponse } from "@/api/auth"
import { useAuthStore } from "@/store/useAuthStore"
import Login from "./Login"

const completedUser: CurrentUserResponse = {
  user_id: 42,
  username: "operator",
  first_name: "Test",
  last_name: "Operator",
  role: "Operator",
  is_active: true,
  created_at: "2026-10-18T12:00:00Z",
  updated_at: "2026-10-18T12:00:00Z",
  password_changed_at: null,
  last_login: "2026-10-18T12:00:00Z",
}

vi.mock("@/pages/auth/MfaLoginFlow", async () => {
  const React = await import("react")
  return {
    MfaLoginFlow: ({
      onAuthenticated,
      initialMessage,
    }: {
      onAuthenticated: (user: CurrentUserResponse) => void
      initialMessage?: string
    }) =>
      React.createElement(
        React.Fragment,
        null,
        initialMessage ? React.createElement("p", null, initialMessage) : null,
        React.createElement(
          "button",
          { onClick: () => onAuthenticated(completedUser) },
          "Complete MFA",
        ),
      ),
  }
})

function LocationDisplay() {
  const location = useLocation()
  return <p data-testid="location">{location.pathname}</p>
}

function renderLogin() {
  const queryClient = new QueryClient()
  useAuthStore.setState({ role: null, username: null, userId: null, sessionEpoch: 0 })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/login"]}>
        <LocationDisplay />
        <Login />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("Login MFA activation", () => {
  it("uses the MFA flow and only populates client auth after completed MFA", async () => {
    const user = userEvent.setup()
    renderLogin()

    expect(useAuthStore.getState().role).toBeNull()
    expect(screen.getByTestId("location")).toHaveTextContent("/login")
    await user.click(screen.getByRole("button", { name: "Complete MFA" }))

    expect(useAuthStore.getState()).toMatchObject({
      role: "Operator",
      username: "operator",
      userId: 42,
    })
    expect(screen.getByTestId("location")).toHaveTextContent("/user")
  })

  it("consumes an existing session-loss message without persisting credentials", () => {
    window.sessionStorage.setItem("auth-message", "Your session expired.")
    renderLogin()

    expect(screen.getByText("Your session expired.")).toBeInTheDocument()
    expect(window.sessionStorage.getItem("auth-message")).toBeNull()
  })
})
