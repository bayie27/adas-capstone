import type { CameraAiStatus, CameraConnectionStatus, CameraRecord } from "@/types/cameras"

export const CAMERA_CONNECTION_STATUS_OPTIONS: Array<{
  label: string
  value: CameraConnectionStatus | "all"
}> = [
  { label: "All Connections", value: "all" },
  { label: "Connected", value: "Connected" },
  { label: "Disconnected", value: "Disconnected" },
  { label: "Reconnecting", value: "Reconnecting" },
  { label: "Unresponsive", value: "Unresponsive" },
]

export const CAMERA_AI_STATUS_OPTIONS: Array<{
  label: string
  value: CameraAiStatus | "all"
}> = [
  { label: "All AI States", value: "all" },
  { label: "Active", value: "Active" },
  { label: "Inactive", value: "Inactive" },
  { label: "Paused", value: "Paused" },
  { label: "Unresponsive", value: "Unresponsive" },
]

export function getCameraConnectionClass(status: CameraConnectionStatus) {
  if (status === "Connected") {
    return "text-emerald-500"
  }

  if (status === "Reconnecting") {
    return "text-amber-500"
  }

  return "text-[#ef4444]"
}

export function getCameraAiClass(status: CameraAiStatus) {
  if (status === "Active") {
    return "text-emerald-500"
  }

  if (status === "Paused") {
    return "text-amber-500"
  }

  return "text-[#ef4444]"
}

export function buildCameraUpdatePayload(
  current: CameraRecord,
  next: { camera_name: string; channel_id: number; is_enabled?: boolean },
) {
  const payload: {
    camera_name?: string
    channel_id?: number
    is_enabled?: boolean
  } = {}

  if (next.camera_name !== current.camera_name) {
    payload.camera_name = next.camera_name
  }

  if (next.channel_id !== current.channel_id) {
    payload.channel_id = next.channel_id
  }

  if (typeof next.is_enabled === "boolean" && next.is_enabled !== current.is_enabled) {
    payload.is_enabled = next.is_enabled
  }

  return payload
}
