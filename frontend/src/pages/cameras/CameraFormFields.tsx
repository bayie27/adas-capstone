import { Input } from "@/components/ui/Input"
import type { CameraFieldErrors, CameraFormState } from "@/pages/cameras/cameraForm"

/** The two fields `146:7278` (Add) and `146:7342` (Edit) both draw. */
export function CameraFormFields({
  form,
  errors,
  disabled,
  cameraNamePlaceholder,
  channelPlaceholder,
  onChange,
}: {
  form: CameraFormState
  errors: CameraFieldErrors
  disabled?: boolean
  cameraNamePlaceholder?: string
  channelPlaceholder?: string
  onChange: (field: keyof CameraFormState, value: string) => void
}) {
  return (
    <>
      <Input
        label="Camera name"
        value={form.camera_name}
        error={errors.camera_name}
        disabled={disabled}
        placeholder={cameraNamePlaceholder}
        onChange={(event) => onChange("camera_name", event.target.value)}
      />
      <Input
        label="Channel No."
        value={form.channel_id}
        error={errors.channel_id}
        disabled={disabled}
        // Text rather than number: a number input silently accepts "1e3" and
        // scroll-wheels the value under the cursor, neither of which is
        // wanted for an identifier the AI engine keys a stream off.
        inputMode="numeric"
        placeholder={channelPlaceholder}
        onChange={(event) => onChange("channel_id", event.target.value)}
      />
    </>
  )
}
