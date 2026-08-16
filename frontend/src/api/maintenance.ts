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
  current_password: string
  confirmation: string
}

export interface RestoreTriggerResponse {
  detail: string
  backup_id: string
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
  "requested" | "in_progress" | "db_restored" | "completed" | "failed" | "rolled_back"

export interface RestoreStateRead {
  status: RestoreStatus
  backup_id: string
  requested_at: string
  requested_by: string | null
  emergency_backup_id: string | null
  steps: RestoreStepRead[]
  error: string | null
  completed_at: string | null
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
 * placeholder/validation can't drift from what a 422 actually demands. */
export function expectedRestoreConfirmation(backupId: string) {
  return `RESTORE ${backupId}`
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
