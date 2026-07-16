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
  detectionAudio.play().catch((err) => {
    console.warn("[detectionSound] Autoplay blocked or failed:", err)
  })
}

export const stopDetectionSound = () => {
  if (!detectionAudio) return
  detectionAudio.pause()
  detectionAudio.currentTime = 0
}
