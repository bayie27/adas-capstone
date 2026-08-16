import { beforeEach, describe, expect, it } from "vitest"

import { useExportJobsStore } from "./useExportJobsStore"

const JOB = {
  jobId: "job-1",
  reportType: "incidents" as const,
  format: "csv" as const,
  createdAt: "2026-01-01T00:00:00Z",
}

describe("useExportJobsStore", () => {
  beforeEach(() => {
    window.localStorage.clear()
    useExportJobsStore.setState({ jobs: [] })
  })

  it("tracks a job and persists it to localStorage", () => {
    useExportJobsStore.getState().track(JOB)
    expect(useExportJobsStore.getState().jobs).toEqual([JOB])
    expect(JSON.parse(window.localStorage.getItem("adas-tracked-export-jobs") ?? "[]")).toEqual([
      JOB,
    ])
  })

  it("caps tracked jobs at 20, dropping the oldest", () => {
    for (let i = 0; i < 25; i++) {
      useExportJobsStore.getState().track({ ...JOB, jobId: `job-${i}` })
    }
    const jobs = useExportJobsStore.getState().jobs
    expect(jobs).toHaveLength(20)
    expect(jobs[0].jobId).toBe("job-24")
    expect(jobs.some((j) => j.jobId === "job-0")).toBe(false)
  })

  it("untracks a job by id", () => {
    useExportJobsStore.getState().track(JOB)
    useExportJobsStore.getState().untrack(JOB.jobId)
    expect(useExportJobsStore.getState().jobs).toEqual([])
  })
})
