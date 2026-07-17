import { useEffect, useState } from "react"

/**
 * Returns a copy of `value` that only updates after it has stopped changing for
 * `delayMs`. Unlike `useDeferredValue` (which defers render priority but still
 * settles on every intermediate value), this coalesces rapid changes over time,
 * so a value driving a query key fires roughly one request per typing pause
 * instead of one per keystroke.
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(id)
  }, [value, delayMs])

  return debounced
}
