import { create } from "zustand"

import type { RealtimeAlertPayload } from "@/types/realtime"
import { playDetectionSound, stopDetectionSound } from "@/utils/detectionSound"

const MAX_ACTIVE_ALERTS = 5
const HANDLED_IDS_KEY = "adas-handled-alert-ids"

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

interface AlertState {
  alerts: RealtimeAlertPayload[]
  /** log_ids dismissed or confirmed this session — persisted to sessionStorage */
  handledIds: Set<number>
  addAlert: (alert: RealtimeAlertPayload) => void
  removeAlert: (logId: number) => void
  clearAlerts: () => void
}

// Drive the alarm off the single fact that matters — whether the active queue
// is non-empty. Playing/stopping on the 0<->non-0 edge means the siren starts
// once when the first alert arrives and stops the moment the queue empties,
// regardless of whether the removal came from a REST action, a WS broadcast,
// or logout.
const syncSound = (before: number, after: number) => {
  if (after > 0 && before === 0) playDetectionSound()
  if (after === 0 && before > 0) stopDetectionSound()
}

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  handledIds: readHandledIds(),
  addAlert: (alert) => {
    const before = get().alerts.length
    set((state) => {
      // If the alert is now Dismissed or Resolved, it should definitely be removed
      // from the active queue and marked as handled.
      if (alert.detection_status === "Dismissed" || alert.detection_status === "Resolved") {
        const nextHandled = new Set([...state.handledIds, alert.log_id])
        writeHandledIds(nextHandled)
        return {
          alerts: state.alerts.filter((a) => a.log_id !== alert.log_id),
          handledIds: nextHandled,
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

      // Truly new alert: prepend and cap
      return {
        alerts: [alert, ...state.alerts].slice(0, MAX_ACTIVE_ALERTS),
      }
    })
    syncSound(before, get().alerts.length)
  },
  removeAlert: (logId) => {
    const before = get().alerts.length
    set((state) => {
      const next = new Set([...state.handledIds, logId])
      writeHandledIds(next)
      return {
        alerts: state.alerts.filter((alert) => alert.log_id !== logId),
        handledIds: next,
      }
    })
    syncSound(before, get().alerts.length)
  },
  clearAlerts: () => {
    stopDetectionSound()
    clearHandledIds()
    set({ alerts: [], handledIds: new Set() })
  },
}))
