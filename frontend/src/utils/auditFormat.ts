/**
 * Formatting helpers for the audit log detail drawer.
 *
 * Every `detail` payload the backend records is a free-form
 * `dict[str, Any]` — the shapes are documented in the implementation plan.
 * This module centralises the logic that turns those raw payloads into
 * human-readable UI text so `AuditLog.tsx` stays a layout-only file.
 */

// ---------------------------------------------------------------------------
// 1. Human-readable key labels
// ---------------------------------------------------------------------------

/**
 * Maps raw snake_case detail keys to human-friendly labels. Keys not listed
 * here fall through to `humanizeDetailKey`'s generic title-casing.
 */
const DETAIL_KEY_LABELS: Record<string, string> = {
  trigger: "Triggered By",
  checks: "Validation Checks",
  backup_id: "Backup ID",
  camera_name: "Camera Name",
  camera_id: "Camera ID",
  channel_id: "Channel ID",
  changed_fields: "Changed Fields",
  reason: "Reason",
  error_type: "Error Type",
  status: "Status",
  from: "Previous Role",
  to: "New Role",
  snoozed_until: "Snoozed Until",
  format: "Export Format",
}

/**
 * Turn a raw snake_case key into a display label.
 * Looks up the curated map first, then falls back to replacing underscores
 * with spaces and title-casing each word.
 */
export function humanizeDetailKey(key: string): string {
  if (DETAIL_KEY_LABELS[key]) return DETAIL_KEY_LABELS[key]
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

/**
 * Display-layer mapping for validation check keys (e.g. backup checks).
 * Matches the Maintenance page labels for consistent terminology across the system.
 */
const CHECK_LABELS: Record<string, string> = {
  checksum: "File Integrity",
  quick_check: "Database Structure",
  foreign_key_check: "Data Links",
}

/**
 * Returns the friendly label for a check key (e.g. "checksum" -> "File Integrity"),
 * or a formatted version of the key as fallback.
 */
export function formatCheckLabel(key: string): string {
  if (CHECK_LABELS[key]) return CHECK_LABELS[key]
  return key
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

/**
 * Maps raw `target_type` values to human-friendly labels. Values not listed
 * here fall back to title-casing so a new backend-side target type degrades
 * gracefully instead of rendering lowercase and raw.
 */
const TARGET_TYPE_LABELS: Record<string, string> = {
  backup: "Backup",
  camera: "Camera",
  export: "Export",
  incident: "Incident",
  restore: "Restore Point",
  session: "Session",
  user: "User",
}

/**
 * Turn a raw `target_type` value into a display label.
 * Looks up the curated map first, then falls back to replacing underscores
 * with spaces and title-casing each word.
 */
export function formatTargetType(targetType: string): string {
  if (TARGET_TYPE_LABELS[targetType]) return TARGET_TYPE_LABELS[targetType]
  return targetType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// 2. UUID / long-ID helpers
// ---------------------------------------------------------------------------

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Returns true when `value` matches the 8-4-4-4-12 UUID shape. */
export function isUuid(value: string): boolean {
  return UUID_RE.test(value)
}

/**
 * Truncates a long identifier for display while preserving recognisability.
 * Short strings (≤ `maxLen`) are returned unchanged.
 *
 * Example: `"458f0a83-c7f0-4db5-9876-c5415f7b89f6"` → `"458f0a83…7b89f6"`
 */
export function truncateId(id: string, maxLen = 16): string {
  if (id.length <= maxLen) return id
  const head = id.slice(0, 8)
  const tail = id.slice(-6)
  return `${head}…${tail}`
}

// ---------------------------------------------------------------------------
// 3. Value classification helpers
// ---------------------------------------------------------------------------

/** True when the value is a non-null, non-array plain object. */
export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

// ---------------------------------------------------------------------------
// 4. Detail-key labelling for known opaque-ID fields
// ---------------------------------------------------------------------------

/**
 * Keys whose values are raw database IDs with no human-readable name
 * available in the current payload. The UI should append a clarifying suffix
 * so an operations lead doesn't mistake `2` for something meaningful.
 */
const OPAQUE_ID_KEYS = new Set(["camera_id", "channel_id"])

/** True when this key holds an opaque numeric ID that has no name alongside it. */
export function isOpaqueIdKey(key: string): boolean {
  return OPAQUE_ID_KEYS.has(key)
}

/**
 * Maps an opaque-id key to the sibling key that, if present in the same
 * detail payload, already spells out its human-readable name (P25 audit
 * target labels — e.g. `camera_id` next to `camera_name`).
 */
const OPAQUE_ID_NAME_KEYS: Record<string, string> = {
  camera_id: "camera_name",
}

/**
 * True when `detailKey`'s id is already explained by a sibling key in the
 * same `detail` payload, so appending the opaque-id suffix would just
 * repeat information the row already shows.
 */
export function hasResolvedName(
  detailKey: string,
  detail: Record<string, unknown> | null | undefined,
): boolean {
  const nameKey = OPAQUE_ID_NAME_KEYS[detailKey]
  return nameKey !== undefined && typeof detail?.[nameKey] === "string"
}

// ---------------------------------------------------------------------------
// 5. Humanise known enum/reason values
// ---------------------------------------------------------------------------

const REASON_LABELS: Record<string, string> = {
  wrong_password: "Incorrect password",
  inactive_account: "Account is deactivated",
  user_not_found: "User not found",
  rate_limited: "Rate limit exceeded",
  locked_out: "Account temporarily locked",
  self_delete: "Cannot delete own account",
  last_admin_delete: "Cannot delete last administrator",
  last_admin_demote: "Cannot demote last administrator",
  last_admin_deactivate: "Cannot deactivate last administrator",
  already_running: "Maintenance operation already in progress",
  confirmation_mismatch: "Confirmation text does not match",
  invalid_backup_id: "Invalid backup ID",
  not_a_valid_restore_point: "Backup is not a valid restore point",
}

/**
 * If the value is a known internal reason code, return a human-readable
 * version. Otherwise format snake_case into Title Case.
 */
export function humanizeReasonValue(value: string): string | null {
  if (REASON_LABELS[value]) return REASON_LABELS[value]
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// 6. Format a `changed_fields` array into a readable string
// ---------------------------------------------------------------------------

export function formatChangedFields(fields: unknown[]): string {
  return fields
    .map((f) =>
      typeof f === "string"
        ? f.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
        : String(f),
    )
    .join(", ")
}
