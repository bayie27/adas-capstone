import { useEffect, useRef } from "react"

import { WS_BASE_URL } from "@/utils/env"

const WS_URL = `${WS_BASE_URL}/ws/alerts`

interface UseAdasWebSocketOptions {
  enabled?: boolean
  reconnectDelayMs?: number
}

export function useAdasWebSocket(
  onMessage: (data: unknown) => void,
  { enabled = true, reconnectDelayMs = 1500 }: UseAdasWebSocketOptions = {},
) {
  const onMessageRef = useRef(onMessage)

  useEffect(() => {
    onMessageRef.current = onMessage
  })

  useEffect(() => {
    if (!enabled) {
      return
    }

    let reconnectTimer: number | null = null
    let websocket: WebSocket | null = null
    let isDisposed = false
    let attempt = 0

    const connect = () => {
      if (isDisposed) {
        return
      }

      websocket = new WebSocket(WS_URL)

      websocket.onopen = () => {
        attempt = 0
      }

      websocket.onmessage = (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data as string)
          onMessageRef.current(parsed)
        } catch {
          return
        }
      }

      websocket.onclose = () => {
        if (isDisposed) {
          return
        }

        // Capped exponential backoff with jitter: exponential stops the
        // reconnect hammering while the backend is down, the 30s cap keeps
        // recovery prompt for an ops console, and the jitter de-synchronizes
        // multiple open tabs so they don't reconnect in the same instant.
        const backoff = Math.min(30_000, reconnectDelayMs * 2 ** attempt) + Math.random() * 500
        attempt += 1
        reconnectTimer = window.setTimeout(connect, backoff)
      }

      websocket.onerror = (error) => {
        if (isDisposed) {
          return
        }

        console.error("[useAdasWebSocket] WebSocket error:", error)
        websocket?.close()
      }
    }

    connect()

    return () => {
      isDisposed = true

      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer)
      }

      if (
        websocket &&
        (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)
      ) {
        websocket.close()
      }
    }
  }, [enabled, reconnectDelayMs])
}
