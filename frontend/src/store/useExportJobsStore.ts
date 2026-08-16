import { create } from "zustand"

import type { ExportJobFormat, ExportJobReportType } from "@/api/exports"

const TRACKED_JOBS_KEY = "adas-tracked-export-jobs"
// A generous cap, not a real limit — this is a convenience list of jobs this
// browser itself created, not the account-wide history the backend has no
// endpoint to return (there is no `GET /api/exports/jobs` list route).
const MAX_TRACKED_JOBS = 20

export interface TrackedExportJob {
  jobId: string
  reportType: ExportJobReportType | "retraining"
  format: ExportJobFormat | "zip"
  createdAt: string
}

function readTrackedJobs(): TrackedExportJob[] {
  try {
    const raw = window.localStorage.getItem(TRACKED_JOBS_KEY)
    if (!raw) return []
    return JSON.parse(raw) as TrackedExportJob[]
  } catch {
    return []
  }
}

function writeTrackedJobs(jobs: TrackedExportJob[]) {
  try {
    window.localStorage.setItem(TRACKED_JOBS_KEY, JSON.stringify(jobs))
  } catch {
    // localStorage unavailable (private browsing, quota) — degrade to
    // in-memory only for this tab rather than throwing.
  }
}

interface ExportJobsState {
  jobs: TrackedExportJob[]
  track: (job: TrackedExportJob) => void
  untrack: (jobId: string) => void
}

/**
 * Jobs this browser has created, persisted to localStorage so they survive a
 * reload or a later session — "an operator can retrieve a completed export
 * from an earlier session" within the limit of what the backend can answer:
 * there is no server-side "list my jobs" endpoint, only
 * `GET /api/exports/jobs/{id}`, so this is a client-side memory of ids to
 * poll, not an account-wide history.
 */
export const useExportJobsStore = create<ExportJobsState>((set, get) => ({
  jobs: readTrackedJobs(),
  track: (job) => {
    const next = [job, ...get().jobs].slice(0, MAX_TRACKED_JOBS)
    writeTrackedJobs(next)
    set({ jobs: next })
  },
  untrack: (jobId) => {
    const next = get().jobs.filter((tracked) => tracked.jobId !== jobId)
    writeTrackedJobs(next)
    set({ jobs: next })
  },
}))
