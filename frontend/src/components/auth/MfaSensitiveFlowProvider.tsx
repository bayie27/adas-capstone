import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react"

import { RecoveryCodesPanel } from "@/pages/auth/RecoveryCodesPanel"
import { MfaSensitiveFlowContext, type ShowMfaRecoveryCodesOptions } from "./mfaSensitiveFlow"

export function MfaSensitiveFlowProvider({ children }: { children: ReactNode }) {
  const [display, setDisplay] = useState<ShowMfaRecoveryCodesOptions | null>(null)
  const displayRef = useRef<ShowMfaRecoveryCodesOptions | null>(null)
  const dialogRef = useRef<HTMLDivElement | null>(null)

  const showCodes = useCallback((options: ShowMfaRecoveryCodesOptions) => {
    displayRef.current = options
    setDisplay(options)
  }, [])

  const clearCodes = useCallback(() => {
    displayRef.current = null
    setDisplay(null)
  }, [])

  const acknowledge = useCallback(() => {
    const current = displayRef.current
    if (!current) return
    displayRef.current = null
    setDisplay(null)
    current.onAcknowledged()
  }, [])

  useEffect(() => {
    if (display) dialogRef.current?.focus()
  }, [display])

  useEffect(() => {
    return () => {
      displayRef.current = null
    }
  }, [])

  function keepFocusInside(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab") return
    const dialog = dialogRef.current
    if (!dialog) return
    const focusable = Array.from(
      dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      ),
    )
    if (focusable.length === 0) {
      event.preventDefault()
      dialog.focus()
      return
    }

    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <MfaSensitiveFlowContext.Provider value={{ showCodes, clearCodes }}>
      <div inert={display !== null} aria-hidden={display !== null ? true : undefined}>
        {children}
      </div>
      {display ? (
        <div className="fixed inset-0 z-[10000] overflow-y-auto bg-canvas p-4 sm:p-8">
          <div className="flex min-h-full items-center justify-center">
            <div
              ref={dialogRef}
              role="dialog"
              aria-modal="true"
              aria-label="Save your recovery codes"
              tabIndex={-1}
              onKeyDown={keepFocusInside}
              className="w-full max-w-[560px] outline-none"
            >
              <RecoveryCodesPanel
                codes={display.codes}
                accountName={display.accountName}
                onAcknowledged={acknowledge}
              />
            </div>
          </div>
        </div>
      ) : null}
    </MfaSensitiveFlowContext.Provider>
  )
}
