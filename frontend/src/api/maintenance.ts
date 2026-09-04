import api from "@/api/client"

/** `08_PKG_backup_ops.md` Steps 4-5 — never includes `artifact_path` or any
 * absolute filesystem path (01_CONTRACTS.md §1.6). There is no download
 * route: a backup lives server-side, listed here and restored via the
 * request flow below, never streamed to a client. */
export interface BackupRead {
  backup_id: string
  created_at: string
  origin: string
  file_size: number
  valid: boolean
  checks: Record<string, boolean>
  storage_tier: "protected" | "degraded"
  storage_reason: string | null
}

export interface BackupListResponse {
  total_filtered: number
  items: BackupRead[]
}

export interface BackupTriggerResponse {
  detail: string
}

export interface RestoreRequestParams {
  backup_id: string
  storage_tier: "protected" | "degraded"
  current_password: string
  confirmation: string
}

export interface RestoreTriggerResponse {
  detail: string
  backup_id: string
  storage_tier: "protected" | "degraded"
  request_id: string
  status: "requested"
}

export interface RestoreStepRead {
  name: string
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  ok: boolean | null
  detail: string | null
}

/** `restore_mod`'s status constants — `requested | in_progress | db_restored
 * | completed | failed | rolled_back`. The offline steps only ever advance
 * while the FastAPI process (and therefore this poll) is down, so a fresh
 * GET after the backend comes back is what actually surfaces them — not a
 * live poll racing the shutdown. */
export type RestoreStatus =
  | "requested"
  | "in_progress"
  | "db_restored"
  | "completed"
  | "failed"
  | "rolled_back"
  | "manual_intervention"

export interface RestoreStateRead {
  status: RestoreStatus
  backup_id: string
  storage_tier: "protected" | "degraded"
  requested_at: string
  requested_by: string | null
  request_id: string | null
  emergency_backup_id: string | null
  emergency_storage_tier: "protected" | "degraded"
  steps: RestoreStepRead[]
  error: string | null
  completed_at: string | null
}

export type RestoreCoordinatorState = "unavailable" | "idle" | "executing" | "error"
export type RestoreCoordinatorReason =
  "not_running" | "stale" | "runtime_uncontrolled" | "busy" | "error"

export interface RestoreCoordinatorRead {
  available: boolean
  state: RestoreCoordinatorState
  platform: "windows" | "systemd" | null
  last_seen_at: string | null
  reason: RestoreCoordinatorReason | null
}

export interface BackupSummaryRead {
  backup_id: string
  storage_tier: "protected" | "degraded"
  created_at: string
  valid: boolean
}

export interface LastRestartRead {
  ran_at: string
  downtime_seconds: number | null
  ready: boolean
  exit_code: number
}

export interface MaintenanceStatusRead {
  last_scheduled_backup: BackupSummaryRead | null
  last_manual_backup: BackupSummaryRead | null
  next_scheduled_backup_at: string | null
  backup_overdue: boolean
  maintenance_hour_local: number
  maintenance_timezone: string
  last_restart: LastRestartRead | null
  latest_restore: RestoreStateRead | null
  restore_coordinator: RestoreCoordinatorRead
  protected_backup_available: boolean
  protected_backup_reason: string | null
  protection_state: "protected" | "degraded" | "unavailable"
  latest_protected_backup: BackupSummaryRead | null
  protected_backup_overdue: boolean
  backup_warning: string | null
}

export async function getBackups() {
  const { data } = await api.get<BackupListResponse>("/system/backups")
  return data
}

export async function triggerBackup() {
  const { data } = await api.post<BackupTriggerResponse>("/system/backups")
  return data
}

/** `RestoreRequestIn.expected_confirmation` (`schemas/maintenance.py`) — the
 * exact string the backend checks byte-for-byte, mirrored here so the UI's
 * placeholder/validation can't drift from what a 422 actually demands. The
 * selected backup id is sent separately by the row action and is not part of
 * the phrase an Administrator has to copy or understand. */
export function expectedRestoreConfirmation(_backupId?: string) {
  void _backupId
  return "RESTORE DATABASE"
}

export async function requestRestore(params: RestoreRequestParams) {
  const { data } = await api.post<RestoreTriggerResponse>("/system/restores", params)
  return data
}

/** `null` when no restore has ever been requested. */
export async function getLatestRestore() {
  const { data } = await api.get<RestoreStateRead | null>("/system/restores/latest")
  return data
}

export async function getMaintenanceStatus() {
  const { data } = await api.get<MaintenanceStatusRead>("/system/maintenance/status")
  return data
}
