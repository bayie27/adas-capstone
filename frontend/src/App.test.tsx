import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import App from "./App"
import { useAuthStore } from "@/store/useAuthStore"

vi.mock("@/hooks/useDeliveryBacklog", () => ({
  useDeliveryBacklog: () => null,
}))

vi.mock("@/components/RealtimeAlertsBridge", () => ({
  RealtimeAlertsBridge: () => null,
}))

vi.mock("@/components/GlobalAlerts", () => ({
  GlobalAlerts: () => null,
}))

vi.mock("@/components/MaintenanceNotice", () => ({
  MaintenanceNotice: () => null,
}))

vi.mock("@/components/DeliveryBacklogNotice", () => ({
  DeliveryBacklogNotice: () => null,
}))

vi.mock("@/components/dev/DevPanelTrigger", () => ({
  DevPanelTrigger: () => null,
}))

vi.mock("@/components/exports/ExportJobsTray", () => ({
  ExportJobsTray: () => null,
}))

vi.mock("@/components/alerts/OngoingIncidentsTray", () => ({
  OngoingIncidentsTray: () => null,
}))

vi.mock("@/components/ui/ToastContainer", () => ({
  ToastContainer: () => null,
}))

vi.mock("@/components/layouts/AppLayout", async () => {
  const { Outlet } = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
  return {
    default: () => (
      <div data-testid="app-layout">
        <Outlet />
      </div>
    ),
  }
})

vi.mock("@/pages/Dashboard", () => ({
  default: () => <div data-testid="dashboard-route">Dashboard</div>,
}))

vi.mock("@/pages/AiPerformance", () => ({
  default: () => <div data-testid="ai-performance-route">AI Performance</div>,
}))

vi.mock("@/pages/Cameras", () => ({ default: () => null }))
vi.mock("@/pages/Detections", () => ({ default: () => null }))
vi.mock("@/pages/SystemHealth", () => ({ default: () => null }))
vi.mock("@/pages/ProfileSettings", () => ({ default: () => null }))
vi.mock("@/pages/HelpCenter", () => ({ default: () => null }))
vi.mock("@/pages/Users", () => ({ default: () => null }))
vi.mock("@/pages/AuditLog", () => ({ default: () => null }))
vi.mock("@/pages/Maintenance", () => ({ default: () => null }))

function renderAppAt(path: string, role: "Admin" | "Operator") {
  window.history.replaceState({}, "", path)
  useAuthStore.setState({ role, username: role === "Admin" ? "admin" : "operator", userId: 1 })

  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  )
}

describe("App role routes", () => {
  afterEach(() => {
    useAuthStore.getState().clearSession()
    window.history.replaceState({}, "", "/")
  })

  it("redirects an Operator's stale /user/ai bookmark to /user", async () => {
    renderAppAt("/user/ai", "Operator")

    await waitFor(() => expect(window.location.pathname).toBe("/user"))
    expect(await screen.findByTestId("dashboard-route")).toBeInTheDocument()
    expect(screen.queryByTestId("ai-performance-route")).not.toBeInTheDocument()
  })

  it("keeps AI Performance on the Administrator route", async () => {
    renderAppAt("/admin/ai", "Admin")

    expect(window.location.pathname).toBe("/admin/ai")
    expect(await screen.findByTestId("ai-performance-route")).toBeInTheDocument()
  })
})
