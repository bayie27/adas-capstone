import { useEffect, useRef } from "react"

import { WS_BASE_URL } from "@/utils/env"

const WS_URL = `${WS_BASE_URL}/ws/alerts`

// 01_CONTRACTS.md §9 close-code table — authentication/session failures and
// origin rejection are terminal, never reconnect automatically.
const TERMINAL_CLOSE_CODES = new Set([4001, 4003, 4009])
// Too many connections for this user — still recoverable, but back off hard
// rather than hammering the limit again immediately.
const CONNECTION_LIMIT_CLOSE_CODE = 4008

interface UseAdasWebSocketOptions {
  enabled?: boolean
  reconnectDelayMs?: number
  /** Fired on every close, including ones the hook will reconnect from. */
  onClose?: (code: number) => void
}

export function useAdasWebSocket(
  onMessage: (data: unknown) => void,
  { enabled = true, reconnectDelayMs = 1500, onClose }: UseAdasWebSocketOptions = {},
) {
  const onMessageRef = useRef(onMessage)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onMessageRef.current = onMessage
    onCloseRef.current = onClose
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

      websocket.onclose = (event: CloseEvent) => {
        if (isDisposed) {
          return
        }

        onCloseRef.current?.(event.code)

        if (TERMINAL_CLOSE_CODES.has(event.code)) {
          return
        }

        // Capped exponential backoff with jitter: exponential stops the
        // reconnect hammering while the backend is down, the 30s cap keeps
        // recovery prompt for an ops console, and the jitter de-synchronizes
        // multiple open tabs so they don't reconnect in the same instant.
        // CONNECTION_LIMIT starts partway up the curve so it backs off hard
        // immediately instead of retrying the limit right away.
        const startingAttempt =
          event.code === CONNECTION_LIMIT_CLOSE_CODE ? Math.max(attempt, 4) : attempt
        const backoff =
          Math.min(30_000, reconnectDelayMs * 2 ** startingAttempt) + Math.random() * 500
        attempt = startingAttempt + 1
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
