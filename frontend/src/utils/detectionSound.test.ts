import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  getSoundUrl,
  SOUND_MAP,
  PREVIEW_DURATION_MS,
  setDetectionSound,
  setDetectionSoundVolume,
  previewDetectionSound,
  playDetectionSound,
  stopDetectionSound,
  stopPreviewDetectionSound,
  isAlarmSounding,
} from "./detectionSound"

describe("detectionSound utility", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("resolves correct URLs for known sound keys and falls back to default", () => {
    expect(getSoundUrl("default")).toBe("/detection_sound.mp3")
    expect(getSoundUrl("buzzer")).toBe("/buzzer.mp3")
    expect(getSoundUrl("eas_siren")).toBe("/eas_siren.mp3")
    expect(getSoundUrl("digital_alarm")).toBe("/digital_alarm.mp3")
    expect(getSoundUrl("unknown_sound")).toBe(SOUND_MAP.default)
    expect(getSoundUrl()).toBe(SOUND_MAP.default)
  })

  it("updates sound and volume without throwing", () => {
    expect(() => setDetectionSound("eas_siren", 75)).not.toThrow()
    expect(() => setDetectionSoundVolume(50)).not.toThrow()
    expect(() => playDetectionSound()).not.toThrow()
    expect(() => stopDetectionSound()).not.toThrow()
  })

  it("previews sound by key and volume with 4-second cap", () => {
    expect(PREVIEW_DURATION_MS).toBe(4000)

    const playSpy = vi
      .spyOn(window.HTMLMediaElement.prototype, "play")
      .mockImplementation(() => Promise.resolve())
    const pauseSpy = vi
      .spyOn(window.HTMLMediaElement.prototype, "pause")
      .mockImplementation(() => {})

    expect(() => previewDetectionSound("buzzer", 60)).not.toThrow()
    expect(playSpy).toHaveBeenCalled()

    // Advance time by 4 seconds to trigger automatic pause
    vi.advanceTimersByTime(4000)
    expect(pauseSpy).toHaveBeenCalled()

    // Test zero volume stopping preview
    expect(() => previewDetectionSound("buzzer", 0)).not.toThrow()
    expect(() => stopPreviewDetectionSound()).not.toThrow()

    playSpy.mockRestore()
    pauseSpy.mockRestore()
  })

  it("does not play a preview while the live alarm is sounding, so two different alarms can never overlap", () => {
    const playSpy = vi
      .spyOn(window.HTMLMediaElement.prototype, "play")
      .mockImplementation(() => Promise.resolve())

    playDetectionSound()
    expect(isAlarmSounding()).toBe(true)
    playSpy.mockClear()

    previewDetectionSound("digital_alarm", 60)
    expect(playSpy).not.toHaveBeenCalled()

    stopDetectionSound()
    expect(isAlarmSounding()).toBe(false)

    previewDetectionSound("digital_alarm", 60)
    expect(playSpy).toHaveBeenCalled()

    playSpy.mockRestore()
  })
})
