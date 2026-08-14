import { useCallback, useSyncExternalStore } from "react"

/**
 * The current time, rounded down to the nearest `intervalMs`, re-rendering
 * once per interval while `active`.
 *
 * A dismiss cooldown is a 60-second window, so counting it down needs
 * second-resolution `now`. But re-rendering a table every second forever, on
 * a screen an operator leaves open for a whole shift, buys nothing when
 * nothing is counting down — hence the gate rather than an unconditional
 * interval.
 *
 * The clock is an external mutable source, so it is read through
 * `useSyncExternalStore` rather than mirrored into state and refreshed from
 * an effect. Two things fall out of that, both of which the state version got
 * wrong: the snapshot is correct on the render where `active` first flips
 * true — a `now` captured at mount could be a whole shift stale by then, and
 * would render one frame of a nonsense countdown — and rounding to the
 * interval keeps the snapshot stable between ticks, which is what
 * `getSnapshot` requires.
 */
export function useNow(active: boolean, intervalMs = 1000) {
  const subscribe = useCallback(
    (onStoreChange: () => void) => {
      if (!active) return () => {}

      const timer = window.setInterval(onStoreChange, intervalMs)
      return () => window.clearInterval(timer)
    },
    [active, intervalMs],
  )

  const getSnapshot = useCallback(
    () => Math.floor(Date.now() / intervalMs) * intervalMs,
    [intervalMs],
  )

  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}
