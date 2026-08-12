import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"

/**
 * The providers any component using TanStack Query or a router hook needs.
 * There is no MSW in this project and no shared test wrapper existed before
 * (dev_plan/03_PKG_dev_panel.md Step 6) — service modules are mocked with
 * vi.mock instead.
 *
 * retry is off so a rejected query settles immediately rather than making
 * the test wait out the default backoff.
 */
export function renderWithProviders(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}
