import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import SystemHealth from "./SystemHealth"
import type { SystemHealthLiveResponse, SystemHealthHistoryResponse } from "@/api/health"

vi.mock("@/api/health", async () => {
  const actual = await vi.importActual<typeof import("@/api/health")>("@/api/health")
  return {
    ...actual,
    getSystemHealthLive: vi.fn(),
    getSystemHealthHistory: vi.fn(),
  }
})

import { getSystemHealthLive, getSystemHealthHistory } from "@/api/health"

const mockLive: SystemHealthLiveResponse = {
  collected_at: "2026-08-25T08:00:00Z",
  stale: false,
  host_uptime_seconds: 86400,
  process_uptime_seconds: 3600,
  sample_camera_count: 2,
  avg_inference_latency_ms: 24.5,
  avg_fps: 30.0,
  disk_available: true,
  disk_percent: 45.2,
  disk_used_bytes: 50 * 1024 ** 3,
  disk_available_bytes: 50 * 1024 ** 3,
  disk_total_bytes: 100 * 1024 ** 3,
  cpu_usage: 35.0,
  cpu_usage_available: true,
  cpu_temp: 55.0,
  cpu_temp_available: true,
  ram_usage: 60.0,
  ram_usage_available: true,
  gpu_usage_avg: null,
  gpu_temp_max: null,
  gpu_mem_pct_max: null,
  gpus: [],
  warnings: [],
  state: "healthy",
}

const mockHistory: SystemHealthHistoryResponse = {
  range: "48h",
  points: [
    {
      timestamp: "2026-08-25T07:00:00Z",
      cpu_usage: 32.0,
      gpu_usage: 15.0,
      gpu_temp_peak: 50.0,
      ram_usage: 58.0,
      cpu_temp_avg: 52.0,
      cpu_temp_peak: 56.0,
      gpu_mem_pct_avg: 20.0,
      gpu_mem_pct_peak: 25.0,
      sample_count: 1,
    },
  ],
}

function renderSystemHealth() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <SystemHealth />
    </QueryClientProvider>,
  )
}

describe("SystemHealth page refactored view", () => {
  it("renders retained KPI stat cards and operational banner", async () => {
    vi.mocked(getSystemHealthLive).mockResolvedValue(mockLive)
    vi.mocked(getSystemHealthHistory).mockResolvedValue(mockHistory)

    renderSystemHealth()

    expect(await screen.findByText("System Health")).toBeInTheDocument()
    expect(await screen.findByText("All systems normal")).toBeInTheDocument()

    // Retained 4 KPI StatCards
    expect(screen.getByText("Server Uptime")).toBeInTheDocument()
    expect(screen.getByText("Inference Latency")).toBeInTheDocument()
    expect(screen.getByText("Processing Speed")).toBeInTheDocument()
    expect(screen.getByText("Disk Storage Usage")).toBeInTheDocument()

    // Tooltip info triggers for 4 KPI StatCards
    expect(screen.getByRole("button", { name: "About Server Uptime" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "About Inference Latency" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "About Processing Speed" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "About Disk Storage Usage" })).toBeInTheDocument()
  })

  it("renders retained performance charts and range tabs directly on the page", async () => {
    vi.mocked(getSystemHealthLive).mockResolvedValue(mockLive)
    vi.mocked(getSystemHealthHistory).mockResolvedValue(mockHistory)

    renderSystemHealth()

    // Advance Details accordion is removed
    expect(screen.queryByText("Advance details")).not.toBeInTheDocument()

    // Retained range tabs
    expect(await screen.findByText("Last 48 Hours")).toBeInTheDocument()
    expect(screen.getByText("30-Day Trend")).toBeInTheDocument()

    // Retained 6 performance charts
    expect(screen.getByText("CPU Utilization")).toBeInTheDocument()
    expect(screen.getByText("GPU Utilization")).toBeInTheDocument()
    expect(screen.getByText("GPU Temperature")).toBeInTheDocument()
    expect(screen.getByText("RAM Utilization")).toBeInTheDocument()
    expect(screen.getByText("CPU Temperature")).toBeInTheDocument()
    expect(screen.getByText("GPU Memory")).toBeInTheDocument()
  })

  it("does not render removed hardware health, GPU, engine diagnostics, or machine capacity sections", async () => {
    vi.mocked(getSystemHealthLive).mockResolvedValue(mockLive)
    vi.mocked(getSystemHealthHistory).mockResolvedValue(mockHistory)

    renderSystemHealth()

    await screen.findByText("System Health")

    // Hardware Health removed
    expect(screen.queryByText("Hardware Health")).not.toBeInTheDocument()
    expect(screen.queryByText("Graphics processor")).not.toBeInTheDocument()
    expect(screen.queryByText("Processor & memory")).not.toBeInTheDocument()

    // Engine Diagnostics removed
    expect(screen.queryByText("Engine Diagnostics")).not.toBeInTheDocument()
    expect(screen.queryByText("Two-engine conflict")).not.toBeInTheDocument()
    expect(screen.queryByText("Engine clock skew")).not.toBeInTheDocument()

    // Machine Capacity removed
    expect(screen.queryByText("Machine Capacity")).not.toBeInTheDocument()
    expect(screen.queryByText("Chosen camera capacity")).not.toBeInTheDocument()
    expect(screen.queryByText("FPS band")).not.toBeInTheDocument()

    // GPU Section removed (standalone table header / empty state)
    expect(screen.queryByText("No GPU detected on this machine.")).not.toBeInTheDocument()
  })

  it("renders neutral dot and N/A when 0 cameras are reporting (idle state)", async () => {
    const idleLive: SystemHealthLiveResponse = {
      ...mockLive,
      sample_camera_count: 0,
      avg_inference_latency_ms: null,
      avg_fps: null,
    }
    vi.mocked(getSystemHealthLive).mockResolvedValue(idleLive)
    vi.mocked(getSystemHealthHistory).mockResolvedValue(mockHistory)

    const { container } = renderSystemHealth()

    expect(await screen.findByText("No cameras currently reporting")).toBeInTheDocument()

    // Inference Latency should show N/A, not "Engine error"
    expect(screen.queryByText("Engine error")).not.toBeInTheDocument()
    // Should have neutral dot indicators
    const neutralDots = container.querySelectorAll(".bg-fg-muted.rounded-full")
    expect(neutralDots.length).toBeGreaterThanOrEqual(1)
  })

  it("renders Engine error and red dot when cameras are connected but inference has failed", async () => {
    const errorLive: SystemHealthLiveResponse = {
      ...mockLive,
      sample_camera_count: 2,
      avg_inference_latency_ms: null,
      avg_fps: null,
    }
    vi.mocked(getSystemHealthLive).mockResolvedValue(errorLive)
    vi.mocked(getSystemHealthHistory).mockResolvedValue(mockHistory)

    renderSystemHealth()

    expect(await screen.findByText("System Health")).toBeInTheDocument()

    // Inference Latency and Processing Speed should show "Engine error"
    const engineErrors = await screen.findAllByText("Engine error")
    expect(engineErrors.length).toBe(2)
  })
})
