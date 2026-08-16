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

describe("CameraDetailPanel", () => {
  it("renders nothing when there is no camera", () => {
    render(<CameraDetailPanel camera={null} isOpen onClose={vi.fn()} />)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("renders identity fields and the RTSP-unavailable note", () => {
    render(<CameraDetailPanel camera={CAMERA} isOpen onClose={vi.fn()} />)
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-label", "Front Gate")
    expect(screen.getByText("Channel 3")).toBeInTheDocument()
    expect(screen.getByText("Unavailable")).toBeInTheDocument()
    expect(screen.getByText(/RTSP stream URL/)).toBeInTheDocument()
  })

  it("renders nothing when closed", () => {
    render(<CameraDetailPanel camera={CAMERA} isOpen={false} onClose={vi.fn()} />)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })
})
