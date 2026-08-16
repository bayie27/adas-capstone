export interface DeliveryBacklog {
  pendingCount: number
  oldestPendingAgeSeconds: number | null
  quarantinedCount: number
}

/**
 * The seam for G5. `ai_engine/outbox.py`'s local retry queue for undelivered
 * accident detections has zero backend exposure today, so there is nothing
 * to fetch — this always returns `null`, the same as `useMaintenanceStore`'s
 * `notice` being empty most of the time. The day G5 ships a real endpoint,
 * this becomes a `useQuery` reading it; `DeliveryBacklogNotice` and its mount
 * point in `App.tsx` need no further change — only this function's body
 * changes from a constant to a real fetch.
 */
export function useDeliveryBacklog(): DeliveryBacklog | null {
  return null
}
