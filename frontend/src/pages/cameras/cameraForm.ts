/**
 * The shape and rules behind the Add / Edit camera forms. The two modals
 * held byte-identical copies of this and of the field markup; they now hold
 * one of each.
 *
 * Split from CameraFormFields.tsx because react-refresh requires a component
 * file to export only components — the same reason statusTone.ts sits beside
 * StatusText.tsx.
 */
export type CameraFormState = {
  camera_name: string
  channel_id: string
}

/** Which field a message belongs under. An absent key means nothing wrong. */
export type CameraFieldErrors = Partial<Record<keyof CameraFormState, string>>

export const EMPTY_CAMERA_FORM: CameraFormState = {
  camera_name: "",
  channel_id: "",
}

/**
 * Mirrors the backend's constraints (`camera_name` 1–100, `channel_id` > 0)
 * so an obviously-invalid form never costs a round trip. It is not a
 * substitute for the server's answer — a duplicate name or channel is only
 * knowable there, and that path is handled by the modals themselves.
 */
export function validateCameraForm(form: CameraFormState) {
  const cameraName = form.camera_name.trim()
  const channelId = Number.parseInt(form.channel_id.trim(), 10)
  const errors: CameraFieldErrors = {}

  if (!cameraName) {
    errors.camera_name = "Camera name is required."
  } else if (cameraName.length > 100) {
    errors.camera_name = "Camera name must be 100 characters or fewer."
  }

  if (!Number.isInteger(channelId) || channelId <= 0) {
    errors.channel_id = "Channel number must be a positive whole number."
  }

  return Object.keys(errors).length > 0
    ? { errors, values: null }
    : { errors, values: { camera_name: cameraName, channel_id: channelId } }
}
