import { describe, expect, it, vi } from "vitest"
import {
  getSoundUrl,
  SOUND_MAP,
  setDetectionSound,
  setDetectionSoundVolume,
  previewDetectionSound,
  playDetectionSound,
  stopDetectionSound,
} from "./detectionSound"

describe("detectionSound utility", () => {
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

  it("previews sound by key and volume", () => {
    const playSpy = vi
      .spyOn(window.HTMLMediaElement.prototype, "play")
      .mockImplementation(() => Promise.resolve())
    expect(() => previewDetectionSound("buzzer", 60)).not.toThrow()
    expect(() => previewDetectionSound(80)).not.toThrow()
    expect(() => previewDetectionSound("buzzer", 0)).not.toThrow()
    playSpy.mockRestore()
  })
})
