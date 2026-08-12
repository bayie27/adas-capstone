// 01_CONTRACTS.md §9.5 — merge keys.
//
// The recovery sequence refetches over REST while the socket keeps delivering,
// so a realtime event can arrive carrying state older than what the client
// already holds. Each event family has a monotonic merge key: `updated_at` for
// incidents, `config_version` for cameras. An event whose key is strictly
// older than the cached record's must be dropped; anything else is applied.
//
// Both predicates are deliberately biased towards applying: an unparsable,
// missing or equal key applies. Dropping an event we could not compare would
// mean live alerts silently stopping, which looks exactly like a quiet night.

function parseTimestamp(value: string | null | undefined): number | null {
  if (!value) return null
  const parsed = new Date(value).getTime()
  return Number.isNaN(parsed) ? null : parsed
}

/**
 * Should an incoming incident event be applied over the incident already held?
 *
 * @param incomingUpdatedAt `updated_at` from the event (ISO 8601).
 * @param existingUpdatedAt `updated_at` of the cached incident, if any.
 * @returns `false` only when both keys parse and the incoming one is strictly older.
 */
export function shouldApplyIncidentEvent(
  incomingUpdatedAt: string | null | undefined,
  existingUpdatedAt: string | null | undefined,
): boolean {
  const incoming = parseTimestamp(incomingUpdatedAt)
  const existing = parseTimestamp(existingUpdatedAt)
  if (incoming === null || existing === null) return true
  return incoming >= existing
}

/**
 * Should an incoming camera status event be applied over the camera already held?
 *
 * @param incomingConfigVersion `config_version` from the event.
 * @param existingConfigVersion `config_version` of the cached camera, if any.
 * @returns `false` only when both versions are finite numbers and the incoming
 *   one is strictly older.
 */
export function shouldApplyCameraEvent(
  incomingConfigVersion: number | null | undefined,
  existingConfigVersion: number | null | undefined,
): boolean {
  if (typeof incomingConfigVersion !== "number" || !Number.isFinite(incomingConfigVersion)) {
    return true
  }
  if (typeof existingConfigVersion !== "number" || !Number.isFinite(existingConfigVersion)) {
    return true
  }
  return incomingConfigVersion >= existingConfigVersion
}
