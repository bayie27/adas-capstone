import { create } from "zustand"

import type { AlertLog, IncidentHandledInfo } from "@/api/alerts"
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

function withoutSnooze<T>(map: Record<number, T>, logId: number): Record<number, T> {
  if (!(logId in map)) return map
  const next = { ...map }
  delete next[logId]
  return next
}

interface AlertState {
  alerts: AlertLog[]
  /** log_ids dismissed or confirmed this session — persisted to sessionStorage */
  handledIds: Set<number>
  /** log_id -> snoozed_until (ISO). Shared incident state, mirrored from SNOOZE_ACTIVATED/RE_ALARM. */
  snoozedUntil: Record<number, string>
  /**
   * log_id -> who snoozed it, mirrored from `SNOOZE_ACTIVATED.snoozed_by` (a
   * formatted display name since P21 Step 3, not an id) or from the acting
   * tab's own session username for the tab that performed the snooze itself.
   * `null` means the snoozing user has since been deleted, same as the
   * broadcast's own null case -- distinct from "no entry", which means no
   * snooze is active at all.
   */
  snoozedBy: Record<number, string | null>
  /**
   * log_id -> who handled it, when a *different* operator did.
   *
   * Fed by the `ALERT_STATUS_UPDATE` broadcast, which reaches every connected
   * dashboard — including ones that never made a request. It is the passive
   * half of the same fact the 409 CONFLICT_STATE delivers to the operator who
   * lost a race.
   *
   * Session-scoped and small: one entry per incident whose status changed
   * under someone else's hand while this tab was open.
   */
  handledByOther: Record<number, IncidentHandledInfo>
  /** event_ids applied this connection — 01_CONTRACTS.md §9.1 reconnect-race dedup */
  seenEventIds: string[]
  /**
   * `ConnectionReadyData.connection_id` — the handle that identifies this
   * socket in the backend log, so a user-reported realtime fault ("the
   * alerts stopped updating") can be matched to something server-side
   * instead of being unfalsifiable. Session-scoped; reset on every connect.
   */
  connectionId: string | null
  /** Mirrors utils/datetime.ts's module-level offset into reactive state
   * purely so a component can render it — the correction itself is always
   * applied via correctedNowMs()/formatRelativeDateTime, not by reading this
   * field. 0 until the first CONNECTION_READY lands. */
  clockOffsetMs: number
  /** How many currently-active incidents were new to this client on the
   * most recent reconnect — the honest count behind "N alerts arrived while
   * you were disconnected", not a guess from the buffered-event replay
   * (which only covers the brief window during the recovery fetch itself,
   * not the whole disconnected period). `null` when there is nothing to
   * report, e.g. the very first connection of the session. */
  reconnectSummary: { count: number } | null
  addAlert: (alert: AlertLog) => void
  removeAlert: (logId: number) => void
  clearAlerts: () => void
  activateSnooze: (logId: number, snoozedUntil: string, snoozedBy: string | null) => void
  clearSnooze: (logId: number) => void
  recordHandledByOther: (logId: number, info: IncidentHandledInfo) => void
  isEventSeen: (eventId: string) => boolean
  markEventSeen: (eventId: string) => void
  setConnectionId: (connectionId: string) => void
  setClockOffsetMs: (offsetMs: number) => void
  setReconnectSummary: (count: number) => void
  clearReconnectSummary: () => void
}

// Drive the alarm off the single fact that matters — whether the active
// (non-snoozed) queue is non-empty. Playing/stopping on the 0<->non-0 edge
// Drive the alarm off whether an unsnoozed Unverified detection is in the queue
// requiring urgent operator triage. Confirmed "Ongoing" incidents are monitored
// via the floating tray and do not sound the siren.
const syncSound = (before: number, after: number) => {
  if (after > 0 && before === 0) playDetectionSound()
  if (after === 0 && before > 0) stopDetectionSound()
}

function activeUnverifiedCount(alerts: AlertLog[], snoozedUntil: Record<number, string>): number {
  return alerts.filter(
    (a) => a.detection_status === "Unverified" && !isSnoozedNow(a.log_id, snoozedUntil),
  ).length
}

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  handledIds: readHandledIds(),
  snoozedUntil: {},
  snoozedBy: {},
  handledByOther: {},
  seenEventIds: [],
  connectionId: null,
  clockOffsetMs: 0,
  reconnectSummary: null,
  addAlert: (alert) => {
    const before = activeUnverifiedCount(get().alerts, get().snoozedUntil)
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
          snoozedBy: withoutSnooze(state.snoozedBy, alert.log_id),
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
    syncSound(before, activeUnverifiedCount(get().alerts, get().snoozedUntil))
  },
  removeAlert: (logId) => {
    const before = activeUnverifiedCount(get().alerts, get().snoozedUntil)
    set((state) => {
      const next = new Set([...state.handledIds, logId])
      writeHandledIds(next)
      return {
        alerts: state.alerts.filter((alert) => alert.log_id !== logId),
        handledIds: next,
        snoozedUntil: withoutSnooze(state.snoozedUntil, logId),
        snoozedBy: withoutSnooze(state.snoozedBy, logId),
      }
    })
    syncSound(before, activeUnverifiedCount(get().alerts, get().snoozedUntil))
  },
  clearAlerts: () => {
    stopDetectionSound()
    clearHandledIds()
    set({
      alerts: [],
      handledIds: new Set(),
      snoozedUntil: {},
      snoozedBy: {},
      handledByOther: {},
      seenEventIds: [],
      connectionId: null,
      clockOffsetMs: 0,
      reconnectSummary: null,
    })
  },
  activateSnooze: (logId, snoozedUntil, snoozedBy) => {
    const before = activeUnverifiedCount(get().alerts, get().snoozedUntil)
    set((state) => ({
      snoozedUntil: { ...state.snoozedUntil, [logId]: snoozedUntil },
      snoozedBy: { ...state.snoozedBy, [logId]: snoozedBy },
    }))
    syncSound(before, activeUnverifiedCount(get().alerts, get().snoozedUntil))
  },
  clearSnooze: (logId) => {
    const before = activeUnverifiedCount(get().alerts, get().snoozedUntil)
    set((state) => ({
      snoozedUntil: withoutSnooze(state.snoozedUntil, logId),
      snoozedBy: withoutSnooze(state.snoozedBy, logId),
    }))
    syncSound(before, activeUnverifiedCount(get().alerts, get().snoozedUntil))
  },
  // Deliberately does NOT call syncSound. It writes metadata only — `alerts`
  // and `snoozedUntil` are untouched, so the non-snoozed queue's count cannot
  // move and the 0<->non-0 alarm edge cannot fire. Anything added here that
  // *does* touch either must go through the before/after pattern above.
  recordHandledByOther: (logId, info) => {
    set((state) => ({ handledByOther: { ...state.handledByOther, [logId]: info } }))
  },
  isEventSeen: (eventId) => get().seenEventIds.includes(eventId),
  markEventSeen: (eventId) => {
    set((state) => ({
      seenEventIds: [...state.seenEventIds, eventId].slice(-MAX_SEEN_EVENT_IDS),
    }))
  },
  setConnectionId: (connectionId) => set({ connectionId }),
  setClockOffsetMs: (offsetMs) => set({ clockOffsetMs: offsetMs }),
  setReconnectSummary: (count) => set({ reconnectSummary: { count } }),
  clearReconnectSummary: () => set({ reconnectSummary: null }),
}))
