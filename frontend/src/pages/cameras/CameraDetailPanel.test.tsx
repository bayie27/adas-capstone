import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { CameraDetailPanel } from "./CameraDetailPanel"
import type { CameraRecord } from "@/api/cameras"

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

const NOW = new Date("2026-01-01T00:00:00Z").getTime()

describe("CameraDetailPanel", () => {
  it("renders nothing when there is no camera", () => {
    render(<CameraDetailPanel camera={null} isOpen onClose={vi.fn()} now={NOW} />)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("renders identity fields and the RTSP-unavailable note", () => {
    render(<CameraDetailPanel camera={CAMERA} isOpen onClose={vi.fn()} now={NOW} />)
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-label", "Front Gate")
    expect(screen.getByText("Channel 3")).toBeInTheDocument()
    expect(screen.getByText(/RTSP stream URL/)).toBeInTheDocument()
  })

  it("renders nothing when closed", () => {
    render(<CameraDetailPanel camera={CAMERA} isOpen={false} onClose={vi.fn()} now={NOW} />)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("renders desired state and the convergence gap", () => {
    render(<CameraDetailPanel camera={CAMERA} isOpen onClose={vi.fn()} now={NOW} />)
    expect(screen.getAllByText("Active")).toHaveLength(2)
    expect(screen.getByText(/applied_config_version/)).toBeInTheDocument()
  })

  it("renders the engine telemetry section as unavailable for an Unresponsive camera", () => {
    const unresponsive: typeof CAMERA = {
      ...CAMERA,
      connection_status: "Unresponsive",
      ai_status: "Unresponsive",
    }
    render(<CameraDetailPanel camera={unresponsive} isOpen onClose={vi.fn()} now={NOW} />)
    expect(
      screen.getByText(/CONNECT_FAILED, STREAM_DROPPED or INFERENCE_FAILED/),
    ).toBeInTheDocument()
  })

  it("counts down a cooldown live against the passed-in now", () => {
    const cooling: typeof CAMERA = {
      ...CAMERA,
      ai_status: "Paused",
      desired_ai_state: "Paused",
      desired_state_reason: "cooldown",
      cooldown_until: new Date(NOW + 30_000).toISOString(),
    }
    render(<CameraDetailPanel camera={cooling} isOpen onClose={vi.fn()} now={NOW} />)
    expect(screen.getByText("30s remaining")).toBeInTheDocument()
  })
})
