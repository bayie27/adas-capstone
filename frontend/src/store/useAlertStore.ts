import { create } from "zustand"

import type { AlertLog } from "@/types/alerts"
import { playDetectionSound, stopDetectionSound } from "@/utils/detectionSound"
import { shouldApplyIncidentEvent } from "@/utils/merge"

const HANDLED_IDS_KEY = "adas-handled-alert-ids"
// Reconnect-race dedup only needs to survive the live connection, not a page
// reload — a reload re-runs the full recovery sequence anyway — so this is
// in-memory only, capped so a long session can't grow it unbounded.
const MAX_SEEN_EVENT_IDS = 500

function readHandledIds(): Set<number> {
  try {
    const raw = sessionStorage.getItem(HANDLED_IDS_KEY)
    if (!raw) return new Set()
    return new Set(JSON.parse(raw) as number[])
  } catch {
    return new Set()
  }
}

function writeHandledIds(ids: Set<number>) {
  try {
    sessionStorage.setItem(HANDLED_IDS_KEY, JSON.stringify([...ids]))
  } catch {
    // sessionStorage unavailable — degrade gracefully
  }
}

function clearHandledIds() {
  try {
    sessionStorage.removeItem(HANDLED_IDS_KEY)
  } catch {
    // ignore
  }
}

export function isSnoozedNow(logId: number, snoozedUntil: Record<number, string>): boolean {
  const until = snoozedUntil[logId]
  return Boolean(until) && new Date(until).getTime() > Date.now()
}

function withoutSnooze(
  snoozedUntil: Record<number, string>,
  logId: number,
): Record<number, string> {
  if (!(logId in snoozedUntil)) return snoozedUntil
  const next = { ...snoozedUntil }
  delete next[logId]
  return next
}

interface AlertState {
  alerts: AlertLog[]
  /** log_ids dismissed or confirmed this session — persisted to sessionStorage */
  handledIds: Set<number>
  /** log_id -> snoozed_until (ISO). Shared incident state, mirrored from SNOOZE_ACTIVATED/RE_ALARM. */
  snoozedUntil: Record<number, string>
  /** event_ids applied this connection — 01_CONTRACTS.md §9.1 reconnect-race dedup */
  seenEventIds: string[]
  addAlert: (alert: AlertLog) => void
  removeAlert: (logId: number) => void
  clearAlerts: () => void
  activateSnooze: (logId: number, snoozedUntil: string) => void
  clearSnooze: (logId: number) => void
  isEventSeen: (eventId: string) => boolean
  markEventSeen: (eventId: string) => void
}

// Drive the alarm off the single fact that matters — whether the active
// (non-snoozed) queue is non-empty. Playing/stopping on the 0<->non-0 edge
// means the siren starts once when the first active alert arrives and stops
// the moment the queue empties, regardless of whether the change came from a
// REST action, a WS broadcast, a snooze, or logout.
const syncSound = (before: number, after: number) => {
  if (after > 0 && before === 0) playDetectionSound()
  if (after === 0 && before > 0) stopDetectionSound()
}

function activeCount(alerts: AlertLog[], snoozedUntil: Record<number, string>): number {
  return alerts.filter((a) => !isSnoozedNow(a.log_id, snoozedUntil)).length
}

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  handledIds: readHandledIds(),
  snoozedUntil: {},
  seenEventIds: [],
  addAlert: (alert) => {
    const before = activeCount(get().alerts, get().snoozedUntil)
    set((state) => {
      // 01_CONTRACTS.md §9.5 — drop anything carrying an older merge key than
      // the incident already queued, before it can revert a newer status.
      const queued = state.alerts.find((a) => a.log_id === alert.log_id)
      if (queued && !shouldApplyIncidentEvent(alert.updated_at, queued.updated_at)) {
        return state
      }

      // If the alert is now Dismissed or Resolved, it should definitely be removed
      // from the active queue and marked as handled.
      if (alert.detection_status === "Dismissed" || alert.detection_status === "Resolved") {
        const nextHandled = new Set([...state.handledIds, alert.log_id])
        writeHandledIds(nextHandled)
        return {
          alerts: state.alerts.filter((a) => a.log_id !== alert.log_id),
          handledIds: nextHandled,
          snoozedUntil: withoutSnooze(state.snoozedUntil, alert.log_id),
        }
      }

      // Don't re-add an alert the operator already handled this session
      if (state.handledIds.has(alert.log_id)) return state

      const existingIndex = state.alerts.findIndex((a) => a.log_id === alert.log_id)

      if (existingIndex !== -1) {
        // Update in place (enrichment)
        const nextAlerts = [...state.alerts]
        nextAlerts[existingIndex] = alert
        return { alerts: nextAlerts }
      }

      // Truly new alert: prepend. The queue only holds unhandled alerts and
      // every operator action removes one, so it is self-limiting — never cap
      // it, or a genuine accident alert could be silently discarded.
      return {
        alerts: [alert, ...state.alerts],
      }
    })
    syncSound(before, activeCount(get().alerts, get().snoozedUntil))
  },
  removeAlert: (logId) => {
    const before = activeCount(get().alerts, get().snoozedUntil)
    set((state) => {
      const next = new Set([...state.handledIds, logId])
      writeHandledIds(next)
      return {
        alerts: state.alerts.filter((alert) => alert.log_id !== logId),
        handledIds: next,
        snoozedUntil: withoutSnooze(state.snoozedUntil, logId),
      }
    })
    syncSound(before, activeCount(get().alerts, get().snoozedUntil))
  },
  clearAlerts: () => {
    stopDetectionSound()
    clearHandledIds()
    set({ alerts: [], handledIds: new Set(), snoozedUntil: {}, seenEventIds: [] })
  },
  activateSnooze: (logId, snoozedUntil) => {
    const before = activeCount(get().alerts, get().snoozedUntil)
    set((state) => ({ snoozedUntil: { ...state.snoozedUntil, [logId]: snoozedUntil } }))
    syncSound(before, activeCount(get().alerts, get().snoozedUntil))
  },
  clearSnooze: (logId) => {
    const before = activeCount(get().alerts, get().snoozedUntil)
    set((state) => ({ snoozedUntil: withoutSnooze(state.snoozedUntil, logId) }))
    syncSound(before, activeCount(get().alerts, get().snoozedUntil))
  },
  isEventSeen: (eventId) => get().seenEventIds.includes(eventId),
  markEventSeen: (eventId) => {
    set((state) => ({
      seenEventIds: [...state.seenEventIds, eventId].slice(-MAX_SEEN_EVENT_IDS),
    }))
  },
}))
