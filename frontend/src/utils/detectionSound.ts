// Global singleton for the alarm sound so it can be controlled from anywhere.
// Ownership lives with the alert store (which knows whether an active alert
// exists), not the WebSocket transport.
const detectionAudio = typeof Audio !== "undefined" ? new Audio("/detection_sound.mp3") : null
if (detectionAudio) {
  detectionAudio.loop = true
}

export const playDetectionSound = () => {
  if (!detectionAudio) return
  // Browsers require user interaction before playing audio. Catching the error prevents console spam.
  detectionAudio.play()?.catch((err) => {
    console.warn("[detectionSound] Autoplay blocked or failed:", err)
  })
}

export const stopDetectionSound = () => {
  if (!detectionAudio) return
  detectionAudio.pause()
  detectionAudio.currentTime = 0
}

/**
 * `volume` is 0-100 (the API's scale, and the settings card's slider);
 * `HTMLMediaElement.volume` is 0-1. This was hardcoded to the browser
 * default (1.0) on an alarm an operator cannot mute except by leaving the
 * page — the settings card is the only caller, applying it once on load and
 * again after every successful save.
 */
export const setDetectionSoundVolume = (volume: number) => {
  if (!detectionAudio) return
  detectionAudio.volume = Math.min(100, Math.max(0, volume)) / 100
}

/**
 * A one-shot, unlooped preview at a given volume — for the settings card's
 * "hear it now" affordance, distinct from the looped alarm instance so
 * previewing a volume never starts or stops a live alarm.
 */
export const previewDetectionSound = (volume: number) => {
  if (typeof Audio === "undefined") return
  const preview = new Audio("/detection_sound.mp3")
  preview.volume = Math.min(100, Math.max(0, volume)) / 100
  preview.play()?.catch((err) => {
    console.warn("[detectionSound] Preview blocked or failed:", err)
  })
}
