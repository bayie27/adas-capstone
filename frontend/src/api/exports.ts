import api from "@/api/client"
import { downloadBlobResponse } from "@/utils/download"

/** `ExportJobCreate.report_type` — a `Literal`, so an unlisted value is a 422. */
export type ExportJobReportType = "incidents" | "dashboard" | "performance" | "audit"

export type ExportJobFormat = "csv" | "pdf"

/** `export_job.status` CHECK constraint (`app/models/export.py`). */
export type ExportJobStatus = "queued" | "processing" | "completed" | "failed" | "expired"

/**
 * The only two values the worker ever actually assigns
 * (`services/reports/jobs.py:610,647`) — `row_limit_exceeded` is written
 * only on the *synchronous* route's 413 audit row, never on an `ExportJob`,
 * and nothing in production code assigns `render_error`. `(string & {})`
 * keeps the union open rather than narrowing display logic to two literals
 * that could drift from the backend.
 */
export type ExportJobFailureCategory = "generation_failed" | "artifact_write_failed" | (string & {})

export interface ExportJobCreateParams {
  report_type: ExportJobReportType
  format: ExportJobFormat
  start_date?: string
  end_date?: string
  status?: string[]
  camera_id?: number[]
  user_id?: number[]
  search?: string
  sort_by?: string
  sort_order?: "asc" | "desc"
  /**
   * `report_type: "audit"` only (P21 Step 5, `schemas/exports.py:39-41`).
   * Validated 422 against the same 26-entry AUDIT_ACTIONS catalog the
   * synchronous export route already checks — the filters genuinely reach
   * the worker, which has its own end-to-end test asserting the produced
   * artifact only contains the filtered rows.
   */
  action?: string[]
  result?: string[]
  target_type?: string[]
}

export interface ExportJobCreateResponse {
  job_id: string
  status: ExportJobStatus
}

/** `GET /api/exports/jobs/{id}` poll response. `artifact_path` is
 * deliberately never returned to a client (01_CONTRACTS.md §3.8). */
export interface ExportJobRead {
  job_id: string
  report_type: ExportJobReportType | "retraining"
  format: ExportJobFormat | "zip"
  status: ExportJobStatus
  progress_current: number
  /** Null until the job completes — the worker only ever sets both progress
   * fields together, at the very end (`jobs.py:673-674`). There is no
   * incremental signal while `queued`/`processing`, so a UI must not render
   * a percentage bar against this; an indeterminate state is the honest one. */
  progress_total: number | null
  failure_category: ExportJobFailureCategory | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  expires_at: string | null
}

export interface RetrainingExportParams {
  start_date?: string
  end_date?: string
  camera_id?: number[]
}

/**
 * `GET /api/exports/jobs` (P21 Step 4, `routes/exports.py:107-141`) — scoped
 * to the caller's own jobs by default, for every role including Admin.
 * `all_users` widens it and is Admin-only server-side (a 403 for an
 * Operator); this client never sets it, since the tray only ever needs
 * "my exports," not the whole system's.
 */
export interface GetExportJobsParams {
  status?: ExportJobStatus[]
  all_users?: boolean
  limit?: number
  offset?: number
}

export interface ExportJobListResponse {
  total_filtered: number
  items: ExportJobRead[]
}

export async function listExportJobs(params: GetExportJobsParams = {}) {
  const { data } = await api.get<ExportJobListResponse>("/exports/jobs", { params })
  return data
}

export async function createExportJob(params: ExportJobCreateParams) {
  const { data } = await api.post<ExportJobCreateResponse>("/exports/jobs", params)
  return data
}

export async function getExportJob(jobId: string) {
  const { data } = await api.get<ExportJobRead>(`/exports/jobs/${jobId}`)
  return data
}

/** 404 until the job completes, and again once the artifact is swept
 * (`EXPORT_ARTIFACT_TTL_HOURS`, 72). Callers should only invoke this once a
 * poll has observed `status === "completed"`. */
export async function downloadExportJob(job: ExportJobRead) {
  const response = await api.get<Blob>(`/exports/jobs/${job.job_id}/download`, {
    responseType: "blob",
  })
  downloadBlobResponse(response, `adas_${job.report_type}_export.${job.format}`)
}

/** Admin only, always async — there is no synchronous equivalent (D-010). */
export async function createRetrainingExport(params: RetrainingExportParams) {
  const { data } = await api.post<ExportJobCreateResponse>("/exports/retraining", params)
  return data
}
