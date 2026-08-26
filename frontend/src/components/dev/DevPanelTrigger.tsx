import { Suspense, lazy, useEffect, useState } from "react"
import { RiTerminalBoxLine } from "@remixicon/react"

import { useDevTools } from "@/hooks/useDevTools"
import { focusRing } from "@/components/ui/Button"
import { cn } from "@/utils/cn"

// lazy() so the panel body lands in its own chunk. The gate is a runtime
// probe rather than import.meta.env.DEV (DT-3), which means this code ships
// in the production bundle — it should at least never be *fetched* unless
// the backend says the routes exist.
const DevPanel = lazy(() => import("@/components/dev/DevPanel"))

export function DevPanelTrigger() {
  const { enabled } = useDevTools()
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    if (!enabled) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "d") {
        event.preventDefault()
        setIsOpen((open) => !open)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [enabled])

  if (!enabled) return null

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label="Open dev tools"
        title="Dev tools (Ctrl+Shift+D)"
        className={cn(
          "fixed bottom-16 right-4 z-[9000] flex h-10 w-10 items-center justify-center rounded-full",
          "border border-stroke bg-surface-1 text-fg-muted shadow-overlay transition-colors duration-150",
          "hover:border-stroke-strong hover:text-fg",
          focusRing,
        )}
      >
        <RiTerminalBoxLine size={18} />
      </button>

      {isOpen && (
        <Suspense fallback={null}>
          <DevPanel isOpen={isOpen} onClose={() => setIsOpen(false)} />
        </Suspense>
      )}
    </>
  )
}
