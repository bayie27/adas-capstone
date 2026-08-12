import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useAdasWebSocket } from "./useAdasWebSocket"

/**
 * Regression coverage for the `resetKey` reconnect path: a dev reseed
 * rotates the session cookie without necessarily changing `role`, so the
 * effect needs a dependency that changes on every session swap. This mock
 * lets us assert the old socket is torn down (not left orphaned against a
 * deleted session) and that the teardown itself never masquerades as a
 * server-initiated close.
 */
class MockWebSocket {
  static instances: MockWebSocket[] = []
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  readyState = MockWebSocket.CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onerror: ((event: unknown) => void) | null = null
  closeCallCount = 0

  constructor(public url: string) {
    MockWebSocket.instances.push(this)
  }

  close() {
    this.closeCallCount += 1
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code: 1000 })
  }

  /** Test helper standing in for the server closing the connection. */
  simulateServerClose(code: number) {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code })
  }
}

describe("useAdasWebSocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal("WebSocket", MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("opens exactly one socket on mount", () => {
    renderHook(() => useAdasWebSocket(() => {}, { enabled: true }))
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it("tears down the old socket and opens a new one when resetKey changes, without reporting it as a close", () => {
    const onClose = vi.fn()
    const { rerender } = renderHook(
      ({ resetKey }: { resetKey: number }) =>
        useAdasWebSocket(() => {}, { enabled: true, resetKey, onClose }),
      { initialProps: { resetKey: 0 } },
    )

    const first = MockWebSocket.instances[0]

    act(() => {
      rerender({ resetKey: 1 })
    })

    expect(first.closeCallCount).toBe(1)
    expect(MockWebSocket.instances).toHaveLength(2)
    expect(MockWebSocket.instances[1]).not.toBe(first)
    // A reset-driven teardown is a disposal, not a session-loss signal — the
    // caller (RealtimeAlertsBridge) must not bounce the operator to /login
    // for a socket it closed on purpose.
    expect(onClose).not.toHaveBeenCalled()
  })

  it("still reports a real server-initiated close", () => {
    const onClose = vi.fn()
    renderHook(() => useAdasWebSocket(() => {}, { enabled: true, onClose }))

    act(() => {
      MockWebSocket.instances[0].simulateServerClose(4009)
    })

    expect(onClose).toHaveBeenCalledWith(4009)
  })

  it("drops a message that arrives on the old socket after a resetKey teardown", () => {
    const onMessage = vi.fn()
    const { rerender } = renderHook(
      ({ resetKey }: { resetKey: number }) =>
        useAdasWebSocket(onMessage, { enabled: true, resetKey }),
      { initialProps: { resetKey: 0 } },
    )

    const first = MockWebSocket.instances[0]

    act(() => {
      rerender({ resetKey: 1 })
    })

    // close() is not synchronous on a real WebSocket — a message already in
    // flight on the disposed socket can still land on its `onmessage`.
    act(() => {
      first.onmessage?.({ data: JSON.stringify({ stale: true }) })
    })

    expect(onMessage).not.toHaveBeenCalled()

    act(() => {
      MockWebSocket.instances[1].onmessage?.({ data: JSON.stringify({ stale: false }) })
    })

    expect(onMessage).toHaveBeenCalledWith({ stale: false })
  })
})
