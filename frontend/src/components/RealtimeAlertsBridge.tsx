import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { useAdasWebSocket } from "@/hooks/useAdasWebSocket"
import { getAlerts } from "@/api/alerts"
import { isAuthRedirectSuspended, redirectToLogin } from "@/api/client"
import { useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
import type { AlertLog } from "@/api/alerts"
import type { CameraListResponse } from "@/api/cameras"
import type {
  AlertStatusUpdateData,
  CameraStatusUpdateData,
  EventEnvelope,
  IncidentPayload,
} from "@/api/events"
import { shouldApplyCameraEvent } from "@/utils/merge"
import {
  asAlertStatusUpdateData,
  asCameraStatusUpdateData,
  asIncidentPayload,
  asReAlarmData,
  asSnoozeActivatedData,
  parseEventEnvelope,
} from "@/api/events"

// WS close codes that mean the session itself is gone — 01_CONTRACTS.md §9 —
// mirror the REST 401 -> clearSession -> redirect flow exactly.
const SESSION_LOST_CLOSE_CODES = new Set([4001, 4009])
const ORIGIN_REJECTED_CLOSE_CODE = 4003

function incidentToAlertLog(payload: IncidentPayload): AlertLog {
  return {
    log_id: payload.log_id,
    source_event_id: payload.source_event_id,
    camera_id: payload.camera_id,
    detected_at: payload.detected_at,
    snapshot_url: payload.snapshot_url,
    confidence_score: payload.confidence_score,
    detection_status: payload.detection_status,
    verified_by_id: payload.verified_by_id,
    verified_by_name: payload.verified_by_name,
    verified_at: payload.verified_at,
    closed_by_id: payload.closed_by_id,
    closed_by_name: payload.closed_by_name,
    closed_at: payload.closed_at,
    camera_name: payload.camera_name,
    snoozed_until: payload.snoozed_until,
    snoozed_by_id: payload.snoozed_by_id,
    created_at: payload.created_at,
    updated_at: payload.updated_at,
  }
}

export function RealtimeAlertsBridge() {
  const queryClient = useQueryClient()
  const role = useAuthStore((state) => state.role)
  const sessionEpoch = useAuthStore((state) => state.sessionEpoch)
  const addAlert = useAlertStore((state) => state.addAlert)
  const clearAlerts = useAlertStore((state) => state.clearAlerts)
  const activateSnooze = useAlertStore((state) => state.activateSnooze)
  const recordHandledByOther = useAlertStore((state) => state.recordHandledByOther)
  const currentUserId = useAuthStore((state) => state.userId)
  const clearSnooze = useAlertStore((state) => state.clearSnooze)

  // The recovery sequence (01_CONTRACTS.md §9.5) must run on every accepted
  // connection, not just the first one — CONNECTION_READY is the signal for
  // that, on both the initial connect and every reconnect. Events that
  // arrive mid-recovery are buffered and replayed after, so a REST snapshot
  // fetched during reconnection can never clobber a newer live event.
  const recoveringRef = useRef(false)
  const bufferedEventsRef = useRef<EventEnvelope[]>([])

  useEffect(() => {
    if (!role) {
      clearAlerts()
    }
  }, [role, clearAlerts])

  function applyEnvelope(envelope: EventEnvelope) {
    switch (envelope.type) {
      case "NEW_DETECTION": {
        const incident = asIncidentPayload(envelope.data)
        if (incident) handleIncident(incident)
        return
      }
      case "ALERT_STATUS_UPDATE": {
        const update = asAlertStatusUpdateData(envelope.data)
        if (update) {
          handleIncident(update)
          noteIfHandledByOther(update)
        }
        return
      }
      case "CAMERA_STATUS_UPDATE": {
        const cameraStatus = asCameraStatusUpdateData(envelope.data)
        if (cameraStatus) handleCameraStatus(cameraStatus)
        return
      }
      case "SNOOZE_ACTIVATED": {
        const snooze = asSnoozeActivatedData(envelope.data)
        if (snooze) activateSnooze(snooze.log_id, snooze.snoozed_until)
        return
      }
      case "RE_ALARM": {
        const reAlarm = asReAlarmData(envelope.data)
        if (reAlarm) clearSnooze(reAlarm.log_id)
        return
      }
      case "CONNECTION_READY":
        // handled directly in handleEnvelope, never buffered
        return
    }
  }

  /**
   * `handled_by` / `handled_at` ride every ALERT_STATUS_UPDATE and were parsed
   * and discarded. They are how an operator who made no request learns that a
   * colleague just acted on the incident they are looking at — the 409 only
   * reaches whoever lost a race, but the broadcast reaches everyone.
   *
   * The actor is identified by **id**, not by name: `handled_by` is
   * `format_user_name(user)` ("First Last", falling back to username), and the
   * auth store holds only `username`, so a name comparison would misfire for
   * anyone with a first and last name. `verified_by_id` / `closed_by_id` are on
   * the same payload and are exact.
   */
  function noteIfHandledByOther(update: AlertStatusUpdateData) {
    if (!update.handled_by && !update.handled_at) return

    const actorId = update.action === "confirm" ? update.verified_by_id : update.closed_by_id
    if (actorId !== null && actorId === currentUserId) return

    recordHandledByOther(update.log_id, {
      currentStatus: update.detection_status,
      handledAction: update.action ?? null,
      handledBy: update.handled_by,
      handledAt: update.handled_at,
    })
  }

  function handleIncident(payload: IncidentPayload) {
    addAlert(incidentToAlertLog(payload))

    // The WS payload doesn't carry verified_by/closed_by-adjacent computed
    // fields the table shows in some views, so invalidate rather than
    // trusting the broadcast to be the complete row.
    queryClient.invalidateQueries({ queryKey: ["alerts", "active"] })
  }

  function handleCameraStatus(cameraStatus: CameraStatusUpdateData) {
    // The KPI cards are server-computed over the whole active population, so
    // they cannot be recomputed from one row — the camera the event names may
    // not even be on the page being held. Track whether this event actually
    // moved a counted field, and refetch only then.
    let kpisAreStale = false

    queryClient.setQueriesData<CameraListResponse>(
      { queryKey: ["cameras"] },
      (existingResponse) => {
        if (!existingResponse) {
          return existingResponse
        }

        return {
          ...existingResponse,
          cameras: existingResponse.cameras.map((camera) => {
            if (camera.camera_id !== cameraStatus.camera_id) return camera

            // 01_CONTRACTS.md §9.5 — config_version is the merge key. A status
            // event older than the cached record must not resurrect superseded
            // state; the engine's 3s heartbeat races the recovery refetch.
            if (!shouldApplyCameraEvent(cameraStatus.config_version, camera.config_version)) {
              return camera
            }

            if (
              camera.is_enabled !== cameraStatus.is_enabled ||
              camera.connection_status !== cameraStatus.connection_status ||
              camera.ai_status !== cameraStatus.ai_status
            ) {
              kpisAreStale = true
            }

            return {
              ...camera,
              is_enabled: cameraStatus.is_enabled,
              desired_ai_state: cameraStatus.desired_ai_state,
              desired_state_reason: cameraStatus.desired_state_reason,
              cooldown_until: cameraStatus.cooldown_until,
              config_version: cameraStatus.config_version,
              connection_status: cameraStatus.connection_status,
              ai_status: cameraStatus.ai_status,
            }
          }),
        }
      },
    )
    // The rows themselves need no invalidate — the WS payload carries the
    // complete new camera status, and refetching on every heartbeat-driven
    // status flap would pull the list plus the dropdown copies on other pages
    // for nothing. The kpis object is the exception: it is the one part of the
    // response the event cannot reconstruct.
    if (kpisAreStale) {
      queryClient.invalidateQueries({ queryKey: ["cameras"] })
    }
  }

  async function runRecoverySequence() {
    recoveringRef.current = true
    bufferedEventsRef.current = []

    try {
      const alertsResponse = await getAlerts({
        status: ["Unverified", "Ongoing"],
        limit: 100,
      }).catch(() => null)

      if (alertsResponse) {
        // Add in reverse order so the most recent ends up at the front of the queue
        for (const log of [...alertsResponse.logs].reverse()) {
          addAlert(log)
          // Step 4: rebuild snooze state from the persisted field, never
          // from a previously received WS message.
          if (log.snoozed_until) {
            activateSnooze(log.log_id, log.snoozed_until)
          }
        }
      }

      queryClient.invalidateQueries({ queryKey: ["cameras"] })
    } finally {
      recoveringRef.current = false
      const buffered = bufferedEventsRef.current
      bufferedEventsRef.current = []
      for (const envelope of buffered) {
        applyEnvelope(envelope)
      }
    }
  }

  function handleEnvelope(envelope: EventEnvelope) {
    if (envelope.type === "CONNECTION_READY") {
      void runRecoverySequence()
      return
    }

    const { isEventSeen, markEventSeen } = useAlertStore.getState()
    if (isEventSeen(envelope.event_id)) {
      return
    }
    markEventSeen(envelope.event_id)

    if (recoveringRef.current) {
      bufferedEventsRef.current.push(envelope)
      return
    }

    applyEnvelope(envelope)
  }

  function handleWsClose(code: number) {
    if (SESSION_LOST_CLOSE_CODES.has(code)) {
      // A dev reseed/login-as rotates the session and bumps sessionEpoch,
      // which tears this socket down cleanly before the server-side
      // revalidation sweep ever gets to it (see useAdasWebSocket's
      // resetKey). This guard is the backstop for the rest of that race —
      // same suspension the axios interceptor honors in services/api.ts,
      // so an in-flight reseed can't bounce the operator to /login twice.
      if (isAuthRedirectSuspended()) return
      useAuthStore.getState().clearSession()
      redirectToLogin("Your session expired. Please sign in again.")
      return
    }

    if (code === ORIGIN_REJECTED_CLOSE_CODE) {
      console.error("[RealtimeAlertsBridge] WebSocket origin rejected — this is a config bug.")
    }
  }

  useAdasWebSocket(
    (raw) => {
      const envelope = parseEventEnvelope(raw)
      if (envelope) handleEnvelope(envelope)
    },
    { enabled: Boolean(role), resetKey: sessionEpoch, onClose: handleWsClose },
  )

  return null
}
