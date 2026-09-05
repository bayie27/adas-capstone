import { act, renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useConfirmedClose } from "./useConfirmedClose"

describe("useConfirmedClose", () => {
  it("closes immediately when there is nothing unsaved", () => {
    const onClose = vi.fn()
    const { result } = renderHook(() => useConfirmedClose(false, onClose))

    act(() => result.current.requestClose())

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(result.current.isConfirmOpen).toBe(false)
  })

  it("opens the confirmation instead of closing when dirty", () => {
    const onClose = vi.fn()
    const { result } = renderHook(() => useConfirmedClose(true, onClose))

    act(() => result.current.requestClose())

    expect(onClose).not.toHaveBeenCalled()
    expect(result.current.isConfirmOpen).toBe(true)
  })

  it("closes and dismisses the confirmation on confirmDiscard", () => {
    const onClose = vi.fn()
    const { result } = renderHook(() => useConfirmedClose(true, onClose))

    act(() => result.current.requestClose())
    act(() => result.current.confirmDiscard())

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(result.current.isConfirmOpen).toBe(false)
  })

  it("dismisses the confirmation without closing on cancelDiscard", () => {
    const onClose = vi.fn()
    const { result } = renderHook(() => useConfirmedClose(true, onClose))

    act(() => result.current.requestClose())
    act(() => result.current.cancelDiscard())

    expect(onClose).not.toHaveBeenCalled()
    expect(result.current.isConfirmOpen).toBe(false)
  })
})
