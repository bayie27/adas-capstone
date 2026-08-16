import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import Login from "./Login"
import { useAuthStore } from "@/store/useAuthStore"

vi.mock("@/api/auth", async () => {
  const actual = await vi.importActual<typeof import("@/api/auth")>("@/api/auth")
  return { ...actual, loginUser: vi.fn() }
})

import { loginUser } from "@/api/auth"

function rateLimitError(retryAfterHeader?: string) {
  return {
    isAxiosError: true,
    response: {
      status: 429,
      data: { code: "AUTH_RATE_LIMITED", detail: "Too many attempts. Try again later." },
      headers: retryAfterHeader === undefined ? {} : { "retry-after": retryAfterHeader },
    },
  }
}

function renderLogin() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  useAuthStore.setState({ role: null, username: null, userId: null })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function submitLogin(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Username"), "operator")
  await user.type(screen.getByLabelText("Password"), "hunter2")
  await user.click(screen.getByRole("button", { name: /login/i }))
}

describe("Login rate-limit countdown", () => {
  it("renders a real countdown driven by the Retry-After header and re-enables at zero", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
    vi.mocked(loginUser).mockRejectedValue(rateLimitError("3"))
    renderLogin()

    await submitLogin(user)

    // The exact starting number is timing-fuzzy (useNow floors to the
    // nearest second; some real time elapses between the mutation
    // rejecting and the deadline being set), same as every other countdown
    // in this app -- assert the shape, then drive it all the way to zero.
    const initialButton = await screen.findByRole("button", { name: /try again in \d+s/i })
    expect(initialButton).toBeDisabled()

    await vi.advanceTimersByTimeAsync(4000)
    const reenabled = await screen.findByRole("button", { name: /^login$/i })
    expect(reenabled).toBeEnabled()

    vi.useRealTimers()
  })

  it("falls back to a fixed 60s countdown when Retry-After is absent", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
    vi.mocked(loginUser).mockRejectedValue(rateLimitError(undefined))
    renderLogin()

    await submitLogin(user)

    expect(await screen.findByRole("button", { name: /try again in 6[01]s/i })).toBeDisabled()
    vi.useRealTimers()
  })

  it("falls back to 60s when Retry-After is present but not a valid number", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
    vi.mocked(loginUser).mockRejectedValue(rateLimitError("not-a-number"))
    renderLogin()

    await submitLogin(user)

    expect(await screen.findByRole("button", { name: /try again in 6[01]s/i })).toBeDisabled()
    vi.useRealTimers()
  })

  it("keeps the countdown running even if the operator edits a field mid-wait", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
    vi.mocked(loginUser).mockRejectedValue(rateLimitError("30"))
    renderLogin()

    await submitLogin(user)
    const before = await screen.findByRole("button", { name: /try again in \d+s/i })
    const textBefore = before.textContent

    await user.type(screen.getByLabelText("Username"), "x")
    const after = screen.getByRole("button", { name: /try again in \d+s/i })
    expect(after).toBeDisabled()
    expect(after.textContent).toBe(textBefore)
    vi.useRealTimers()
  })
})
