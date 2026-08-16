import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { CameraDetailPanel } from "./CameraDetailPanel"
import type { CameraDetail, CameraRecord } from "@/api/cameras"

vi.mock("@/api/cameras", async () => {
  const actual = await vi.importActual<typeof import("@/api/cameras")>("@/api/cameras")
  return {
    ...actual,
    getCameraDetail: vi.fn(),
  }
})

import { getCameraDetail } from "@/api/cameras"

const CAMERA: CameraRecord = {
  camera_id: 1,
  camera_name: "Front Gate",
  channel_id: 3,
  connection_status: "Connected",
  ai_status: "Active",
  is_enabled: true,
  is_active: true,
  desired_ai_state: "Active",
  desired_state_reason: null,
  cooldown_until: null,
  config_version: 4,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}

const EMPTY_DETAIL: CameraDetail = {
  ...CAMERA,
  applied_config_version: null,
  last_heartbeat_at: null,
  measured_fps: null,
  inference_latency_ms: null,
  last_error_code: null,
  last_error_message: null,
  rtsp_url_redacted: null,
}

const NOW = new Date("2026-01-01T00:00:00Z").getTime()

function renderPanel(camera: CameraRecord | null, isOpen = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <CameraDetailPanel camera={camera} isOpen={isOpen} onClose={vi.fn()} now={NOW} />
    </QueryClientProvider>,
  )
}

describe("CameraDetailPanel", () => {
  it("renders nothing when there is no camera", () => {
    renderPanel(null)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("renders nothing when closed", () => {
    vi.mocked(getCameraDetail).mockResolvedValue(EMPTY_DETAIL)
    renderPanel(CAMERA, false)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("renders identity fields immediately and telemetry as loading, then real values once the detail fetch resolves", async () => {
    vi.mocked(getCameraDetail).mockResolvedValue({
      ...EMPTY_DETAIL,
      applied_config_version: 4,
      last_heartbeat_at: "2026-01-01T00:00:00Z",
      measured_fps: 12.5,
      inference_latency_ms: 42,
      last_error_code: null,
      last_error_message: null,
      rtsp_url_redacted: "rtsp://***:***@10.0.0.5:554/stream1",
    })
    renderPanel(CAMERA)

    expect(screen.getByRole("dialog")).toHaveAttribute("aria-label", "Front Gate")
    expect(screen.getByText("Channel 3")).toBeInTheDocument()
    expect(screen.getAllByText("Loading…").length).toBeGreaterThan(0)

    await waitFor(() => expect(getCameraDetail).toHaveBeenCalledWith(1))
    expect(await screen.findByText("12.5 fps")).toBeInTheDocument()
    expect(screen.getByText("42 ms")).toBeInTheDocument()
    expect(screen.getByText("None")).toBeInTheDocument()
  })

  it("shows a stale badge when the last heartbeat is older than the staleness threshold", async () => {
    vi.mocked(getCameraDetail).mockResolvedValue({
      ...EMPTY_DETAIL,
      last_heartbeat_at: new Date(NOW - 60_000).toISOString(),
    })
    renderPanel(CAMERA)
    expect(await screen.findByText("Stale")).toBeInTheDocument()
  })

  it("renders the danger-toned error code and its message when present", async () => {
    vi.mocked(getCameraDetail).mockResolvedValue({
      ...EMPTY_DETAIL,
      last_error_code: "CONNECT_FAILED",
      last_error_message: "Could not open RTSP stream",
    })
    renderPanel(CAMERA)
    expect(await screen.findByText("CONNECT_FAILED")).toBeInTheDocument()
    expect(screen.getByText("Could not open RTSP stream")).toBeInTheDocument()
  })

  it("renders Admin only instead of a value when rtsp_url_redacted is null", async () => {
    vi.mocked(getCameraDetail).mockResolvedValue(EMPTY_DETAIL)
    renderPanel(CAMERA)
    expect(await screen.findByText("Admin only")).toBeInTheDocument()
  })

  it("masks the RTSP URL by default and reveals it on toggle", async () => {
    const user = userEvent.setup()
    vi.mocked(getCameraDetail).mockResolvedValue({
      ...EMPTY_DETAIL,
      rtsp_url_redacted: "rtsp://***:***@10.0.0.5:554/stream1",
    })
    renderPanel(CAMERA)

    expect(await screen.findByText("Hidden — masked, no live credentials")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Show stream URL" }))
    expect(screen.getByText("rtsp://***:***@10.0.0.5:554/stream1")).toBeInTheDocument()
  })

  it("renders desired state and the real applied config version", async () => {
    vi.mocked(getCameraDetail).mockResolvedValue({ ...EMPTY_DETAIL, applied_config_version: 4 })
    renderPanel(CAMERA)
    expect(screen.getAllByText("Active")).toHaveLength(2)
    await waitFor(() => expect(screen.getByText("Applied config version")).toBeInTheDocument())
  })

  it("counts down a cooldown live against the passed-in now", async () => {
    vi.mocked(getCameraDetail).mockResolvedValue(EMPTY_DETAIL)
    const cooling: CameraRecord = {
      ...CAMERA,
      ai_status: "Paused",
      desired_ai_state: "Paused",
      desired_state_reason: "cooldown",
      cooldown_until: new Date(NOW + 30_000).toISOString(),
    }
    renderPanel(cooling)
    expect(screen.getByText("30s remaining")).toBeInTheDocument()
  })
})
