import { useMutation } from "@tanstack/react-query"

import { createExportJob, type ExportJobCreateParams } from "@/api/exports"
import { useExportJobsStore } from "@/store/useExportJobsStore"

/**
 * Submits `POST /api/exports/jobs` and tracks the returned job_id in
 * useExportJobsStore so the global tray (ExportJobsTray) picks it up and
 * starts polling — the mutation itself doesn't poll or download anything.
 */
export function useExportJobSubmit() {
  const track = useExportJobsStore((state) => state.track)

  return useMutation({
    mutationFn: (params: ExportJobCreateParams) => createExportJob(params),
    onSuccess: (response, params) => {
      track({
        jobId: response.job_id,
        reportType: params.report_type,
        format: params.format,
        createdAt: new Date().toISOString(),
      })
    },
  })
}
