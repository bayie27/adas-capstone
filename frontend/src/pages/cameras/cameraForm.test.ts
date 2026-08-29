import { describe, expect, it } from "vitest"

import { validateCameraForm } from "@/pages/cameras/cameraForm"

describe("validateCameraForm", () => {
  it("rejects a channel that is not a positive whole number", () => {
    const result = validateCameraForm({
      camera_name: "North Gate",
      channel_id: "12abc",
    })

    expect(result.values).toBeNull()
    expect(result.errors.channel_id).toBe("Channel number must be a positive whole number.")
  })

  it("trims and normalizes a valid camera configuration", () => {
    expect(
      validateCameraForm({
        camera_name: "  North Gate  ",
        channel_id: " 12 ",
      }),
    ).toEqual({
      errors: {},
      values: { camera_name: "North Gate", channel_id: 12 },
    })
  })

  it("reports the required and maximum-length camera-name boundaries", () => {
    expect(validateCameraForm({ camera_name: "   ", channel_id: "1" }).errors.camera_name).toBe(
      "Camera name is required.",
    )
    expect(
      validateCameraForm({ camera_name: "x".repeat(101), channel_id: "1" }).errors.camera_name,
    ).toBe("Camera name must be 100 characters or fewer.")
  })
})
