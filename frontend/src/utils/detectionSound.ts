// Global singleton for the alarm sound so it can be controlled from anywhere.
// Ownership lives with the alert store (which knows whether an active alert
// exists), not the WebSocket transport.

export const SOUND_MAP: Record<string, string> = {
  default: "/detection_sound.mp3",
  buzzer: "/buzzer.mp3",
  eas_siren: "/eas_siren.mp3",
  digital_alarm: "/digital_alarm.mp3",
}

export const getSoundUrl = (key?: string): string => {
  if (key && SOUND_MAP[key]) {
    return SOUND_MAP[key]
  }
  return SOUND_MAP.default
}

export const PREVIEW_DURATION_MS = 4000

let activeSoundKey = "default"
let activeVolume = 80
let previewAudio: HTMLAudioElement | null = null
let previewTimeoutId: ReturnType<typeof setTimeout> | null = null

const detectionAudio = typeof Audio !== "undefined" ? new Audio(getSoundUrl(activeSoundKey)) : null
if (detectionAudio) {
  detectionAudio.loop = true
}

export const setDetectionSound = (soundKey: string, volume?: number) => {
  activeSoundKey = soundKey
  if (detectionAudio) {
    const nextUrl = getSoundUrl(soundKey)
    if (!detectionAudio.src.endsWith(nextUrl)) {
      const isPlaying = !detectionAudio.paused
      detectionAudio.src = nextUrl
      if (isPlaying) {
        detectionAudio.play()?.catch(() => {})
      }
    }
  }
  if (volume !== undefined) {
    setDetectionSoundVolume(volume)
  }
}

export const setDetectionSoundKey = (soundKey: string) => {
  setDetectionSound(soundKey)
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

export const stopPreviewDetectionSound = () => {
  if (previewTimeoutId !== null) {
    clearTimeout(previewTimeoutId)
    previewTimeoutId = null
  }
  if (previewAudio) {
    previewAudio.pause()
    previewAudio.currentTime = 0
    previewAudio = null
  }
}

/**
 * `volume` is 0-100 (the API's scale, and the settings card's slider);
 * `HTMLMediaElement.volume` is 0-1. This was hardcoded to the browser
 * default (1.0) on an alarm an operator cannot mute except by leaving the
 * page — the settings card is the only caller, applying it once on load and
 * again after every successful save.
 */
export const setDetectionSoundVolume = (volume: number) => {
  activeVolume = Math.min(100, Math.max(0, volume))
  if (!detectionAudio) return
  detectionAudio.volume = activeVolume / 100
}

/**
 * A one-shot, unlooped preview at a given sound key and volume with a 4-second
 * duration cap — for the settings card's "hear it now" and dropdown selection
 * affordance, distinct from the looped alarm instance so previewing never
 * starts or stops a live alarm.
 * Stops any previously running preview so rapid clicks don't overlap audio.
 */
export const previewDetectionSound = (
  soundKeyOrVolume: string | number = "default",
  volume?: number,
  durationMs: number = PREVIEW_DURATION_MS,
) => {
  if (typeof Audio === "undefined") return

  let soundKey = activeSoundKey
  let resolvedVolume = activeVolume

  if (typeof soundKeyOrVolume === "number") {
    resolvedVolume = soundKeyOrVolume
  } else {
    soundKey = soundKeyOrVolume
    if (typeof volume === "number") {
      resolvedVolume = volume
    }
  }

  if (resolvedVolume <= 0) {
    stopPreviewDetectionSound()
    return
  }

  stopPreviewDetectionSound()

  const audio = new Audio(getSoundUrl(soundKey))
  previewAudio = audio
  audio.volume = Math.min(100, Math.max(0, resolvedVolume)) / 100
  audio.play()?.catch((err) => {
    console.warn("[detectionSound] Preview blocked or failed:", err)
  })

  if (durationMs > 0) {
    previewTimeoutId = setTimeout(() => {
      if (previewAudio === audio) {
        previewAudio.pause()
        previewAudio.currentTime = 0
        previewAudio = null
      }
      previewTimeoutId = null
    }, durationMs)
  }
}
