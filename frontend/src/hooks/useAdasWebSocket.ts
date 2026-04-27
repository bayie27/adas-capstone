import { useEffect, useRef } from "react"
import { WS_BASE_URL } from "@/config/env"

const WS_URL = `${WS_BASE_URL}/ws/alerts`

/**
 * Connects to the ADAS backend WebSocket alerts stream.
 *
 * @param onMessage - Called with every parsed JSON payload received from the server.
 */
export function useAdasWebSocket(onMessage: (data: unknown) => void) {
  // Keep a stable ref to the callback so the effect never needs to re-run
  // when the consumer re-renders with an inline arrow function.
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    const ws = new WebSocket(WS_URL)

    ws.onmessage = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data as string)
        onMessageRef.current(parsed)
      } catch {
        // Ignore non-JSON frames (e.g. heartbeat pings)
      }
    }

    ws.onerror = (err) => {
      console.error("[useAdasWebSocket] WebSocket error:", err)
    }

    return () => {
      // Clean up: close connection when component unmounts
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
    }
  }, []) // Empty deps – intentional; callback is accessed via ref
}
