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
  report_type: "Report Type",
  mode: "Export Mode",
  row_count: "Row Count",
  job_id: "Job ID",
  failure_category: "Failure Category",
  filters: "Filters",
  sort: "Sorting",
  field: "Sort Field",
  order: "Sort Order",
  target_ref: "Target Reference",
  target_type: "Target Type",
  target_username: "Target Username",
  user_id: "User ID",
  username: "Username",
  role: "Role",
  start_date: "Start Date",
  end_date: "End Date",
  search: "Search Query",
  action: "Action",
  result: "Result",
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

/** True for a long unbroken hex id — e.g. a non-hyphenated backup id
 *  (`uuid4().hex`), which `isUuid` deliberately does not match. */
export function isLongHexId(value: string): boolean {
  return /^[0-9a-f]{24,}$/i.test(value)
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
// 3. Value classification & unset helpers
// ---------------------------------------------------------------------------

/** True when the value is a non-null, non-array plain object. */
export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

/**
 * Identifies null, undefined, blank strings, empty arrays, and objects
 * where all inner properties are unset.
 */
export function isUnsetValue(value: unknown): boolean {
  if (value === null || value === undefined) return true
  if (typeof value === "string") return value.trim().length === 0
  if (Array.isArray(value)) return value.length === 0 || value.every(isUnsetValue)
  if (isPlainObject(value)) {
    const keys = Object.keys(value)
    return keys.length === 0 || Object.values(value).every(isUnsetValue)
  }
  return false
}

/**
 * Filters a nested record to only key-value pairs that are active (non-unset).
 */
export function filterActiveEntries(obj: Record<string, unknown>): Array<[string, unknown]> {
  return Object.entries(obj).filter(([, val]) => !isUnsetValue(val))
}

// ---------------------------------------------------------------------------
// 4. Detail-key labelling for known opaque-ID fields
// ---------------------------------------------------------------------------

/**
 * Keys whose values are raw database IDs with no human-readable name
 * available in the current payload. The UI should append a clarifying suffix
 * so an operations lead doesn't mistake `2` for something meaningful.
 */
const OPAQUE_ID_KEYS = new Set(["camera_id"])

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

/**
 * Resolves a human-readable display label for a target reference.
 * If targetType is "camera", resolves to the camera name if available.
 * If targetType is "user", resolves to the username if available.
 * Otherwise, truncates UUIDs and long hex IDs.
 */
export function formatTargetDisplayName({
  targetType,
  targetRef,
  detail,
  cameraMap,
  userMap,
}: {
  targetType: string | null
  targetRef: string | null
  detail?: Record<string, unknown> | null
  cameraMap?: Map<string, string>
  userMap?: Map<string, string>
}): string {
  if (!targetRef) return ""

  if (targetType === "camera") {
    if (typeof detail?.camera_name === "string" && detail.camera_name.trim().length > 0) {
      return detail.camera_name
    }
    if (cameraMap?.has(targetRef)) {
      return cameraMap.get(targetRef)!
    }
  }

  if (targetType === "user") {
    if (typeof detail?.target_username === "string" && detail.target_username.trim().length > 0) {
      return detail.target_username
    }
    if (typeof detail?.username === "string" && detail.username.trim().length > 0) {
      return detail.username
    }
    if (userMap?.has(targetRef)) {
      return userMap.get(targetRef)!
    }
  }

  if (isUuid(targetRef) || isLongHexId(targetRef)) {
    return truncateId(targetRef)
  }

  return targetRef
}

// ---------------------------------------------------------------------------
// 5. Humanise known enum/reason values & scalar fields
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
  row_limit_exceeded: "Row limit exceeded",
  generation_failed: "Export generation failed",
  artifact_write_failed: "Export file write failed",
}

/**
 * If the value is a known internal reason code, return a human-readable
 * version. Otherwise format snake_case into Title Case.
 */
export function humanizeReasonValue(value: string): string | null {
  if (REASON_LABELS[value]) return REASON_LABELS[value]
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

const REPORT_TYPE_LABELS: Record<string, string> = {
  audit: "Audit Log",
  incidents: "Incident Log",
  performance: "AI Performance",
  dashboard: "Dashboard",
  retraining: "Retraining Package",
}

const MODE_LABELS: Record<string, string> = {
  sync: "Direct Download",
  job: "Background Export",
}

const FORMAT_LABELS: Record<string, string> = {
  csv: "CSV",
  pdf: "PDF",
  zip: "ZIP",
}

const SORT_ORDER_LABELS: Record<string, string> = {
  asc: "Ascending",
  desc: "Descending",
}

const SORT_FIELD_LABELS: Record<string, string> = {
  created_at: "Time",
  user_id: "Actor",
  action: "Action",
  target_type: "Target Type",
  result: "Result",
}

const TRIGGER_LABELS: Record<string, string> = {
  manual: "Manual",
  scheduled: "Scheduled",
}

/**
 * Formats known scalar detail values (enums, modes, formats, reasons)
 * into friendly display text.
 */
export function formatScalarDetailValue(detailKey: string, value: unknown): string {
  if (isUnsetValue(value)) return "Not set"

  const strVal = String(value).trim()

  if (detailKey === "reason" || detailKey === "failure_category") {
    return humanizeReasonValue(strVal) ?? strVal
  }

  if (detailKey === "report_type") {
    return REPORT_TYPE_LABELS[strVal.toLowerCase()] ?? humanizeDetailKey(strVal)
  }

  if (detailKey === "mode") {
    return MODE_LABELS[strVal.toLowerCase()] ?? humanizeDetailKey(strVal)
  }

  if (detailKey === "format") {
    return FORMAT_LABELS[strVal.toLowerCase()] ?? strVal.toUpperCase()
  }

  if (detailKey === "order") {
    return SORT_ORDER_LABELS[strVal.toLowerCase()] ?? strVal
  }

  if (detailKey === "field") {
    return SORT_FIELD_LABELS[strVal.toLowerCase()] ?? humanizeDetailKey(strVal)
  }

  if (detailKey === "trigger") {
    return TRIGGER_LABELS[strVal.toLowerCase()] ?? humanizeDetailKey(strVal)
  }

  if (detailKey === "row_count" && typeof value === "number") {
    return new Intl.NumberFormat("en-US").format(value)
  }

  return strVal
}

// ---------------------------------------------------------------------------
// 6. Format a `changed_fields` array into a readable string
// ---------------------------------------------------------------------------

export function formatChangedFields(fields: unknown[]): string {
  const filtered = fields.filter((f) => !isUnsetValue(f))
  if (filtered.length === 0) return "None"

  return filtered
    .map((f) =>
      typeof f === "string"
        ? f.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
        : String(f),
    )
    .join(", ")
}
