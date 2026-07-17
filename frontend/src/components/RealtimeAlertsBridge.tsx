import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { useAdasWebSocket } from "@/hooks/useAdasWebSocket"
import { getAlerts, getAlertDetails } from "@/services/alerts"
import { useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
import type { CameraListResponse } from "@/types/cameras"
import { normalizeRealtimeAlert, normalizeRealtimeCameraStatus } from "@/utils/realtime"

export function RealtimeAlertsBridge() {
  const queryClient = useQueryClient()
  const token = useAuthStore((state) => state.token)
  const addAlert = useAlertStore((state) => state.addAlert)
  const clearAlerts = useAlertStore((state) => state.clearAlerts)
  const recoveryRanRef = useRef(false)

  // Active Recovery Fetch: on login, seed the alert queue with any open
  // Unverified/Ongoing alerts that existed before this session connected.
  useEffect(() => {
    if (!token) {
      clearAlerts()
      recoveryRanRef.current = false
      return
    }

    if (recoveryRanRef.current) return
    recoveryRanRef.current = true

    getAlerts({ status: ["Unverified"], limit: 100 })
      .then((response) => {
        // Add in reverse order so the most recent ends up at the front of the queue
        for (const log of [...response.logs].reverse()) {
          addAlert({
            type: "NEW_DETECTION",
            log_id: log.log_id,
            camera_id: log.camera_id,
            detected_at: log.detected_at,
            snapshot_path: log.snapshot_path,
            confidence_score: log.confidence_score,
            detection_status: log.detection_status,
            camera_name: log.camera_name,
          })
        }
      })
      .catch(() => {
        // Non-fatal — live WebSocket events will still populate the queue
      })
  }, [token, addAlert, clearAlerts])

  useAdasWebSocket(
    (payload) => {
      const alert = normalizeRealtimeAlert(payload)

      if (alert) {
        // Add immediately with whatever data we have (camera_name may be null)
        addAlert(alert)
        // The WS payload lacks the verified_by/closed_by fields the table shows,
        // so invalidate to refetch complete rows rather than optimistically
        // writing an incomplete one that a refetch would immediately replace.
        queryClient.invalidateQueries({ queryKey: ["alerts", "active"] })

        // Enrich with camera_name if the broadcast didn't include it
        if (!alert.camera_name) {
          getAlertDetails(alert.log_id)
            .then((enriched) => {
              if (enriched?.camera_name) {
                addAlert({ ...alert, camera_name: enriched.camera_name })
              }
            })
            .catch(() => {})
        }

        return
      }

      const cameraStatus = normalizeRealtimeCameraStatus(payload)

      if (!cameraStatus) {
        return
      }

      queryClient.setQueriesData<CameraListResponse>({ queryKey: ["cameras"] }, (existingResponse) => {
        if (!existingResponse) {
          return existingResponse
        }

        return {
          ...existingResponse,
          cameras: existingResponse.cameras.map((camera) =>
            camera.camera_id === cameraStatus.camera_id
              ? {
                  ...camera,
                  connection_status: cameraStatus.connection_status,
                  ai_status: cameraStatus.ai_status,
                }
              : camera,
          ),
        }
      })
      // No invalidate: the WS payload carries the complete new camera status,
      // so patching every cameras query in place is sufficient. Invalidating
      // here would refetch the list plus the dropdown copies on other pages on
      // every status flap of any camera.
    },
    { enabled: Boolean(token) },
  )

  return null
}
