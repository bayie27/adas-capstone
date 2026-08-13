import { useState } from "react"

import { cn } from "@/utils/cn"
import { RiEyeLine, RiEyeOffLine } from "@remixicon/react"

/**
 * Label + password field + eye-toggle. Owns its own visibility state (pure
 * presentation — no parent needs to read it), which deletes the per-field
 * `useState(false)` toggles the pages used to carry. Defaults `autoComplete`
 * to "new-password" so browsers don't autofill an admin's own password into
 * "reset user password" forms.
 */
export function PasswordInput({
  label,
  value,
  onChange,
  autoComplete = "new-password",
  placeholder,
  labelClassName,
  inputClassName,
  toggleClassName,
  iconSize = 14,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  autoComplete?: string
  placeholder?: string
  labelClassName?: string
  inputClassName?: string
  toggleClassName?: string
  iconSize?: number
}) {
  const [visible, setVisible] = useState(false)

  return (
    <div>
      <label className={cn("mb-2 block text-[11px] font-semibold text-[#E4E4E7]", labelClassName)}>
        {label}
      </label>
      <div className="relative">
        <input
          type={visible ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
          placeholder={placeholder}
          className={cn(
            "w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 pr-10 text-sm text-white focus:border-[#555] focus:outline-none",
            inputClassName,
          )}
        />
        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          className={cn(
            "absolute right-3 top-1/2 -translate-y-1/2 text-[#555] transition-colors hover:text-white",
            toggleClassName,
          )}
        >
          {visible ? <RiEyeLine size={iconSize} /> : <RiEyeOffLine size={iconSize} />}
        </button>
      </div>
    </div>
  )
}
