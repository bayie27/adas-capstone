import { useState } from "react"
import { useMutation } from "@tanstack/react-query"

import { createRetrainingExport, type RetrainingExportParams } from "@/api/exports"
import { Button } from "@/components/ui/Button"
import { DateRangePicker } from "@/components/ui/DateRangePicker"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { useExportJobsStore } from "@/store/useExportJobsStore"

/**
 * D-14 owns this panel — Admin only, always async (there is no synchronous
 * retraining route). Its own date range and camera filter, deliberately
 * independent of the page's own search/date/camera filters above: the
 * performance table above is a read view of what already happened, this is
 * a training-data cut with its own scope.
 *
 * Lives on AiPerformance rather than waiting for Phase 18's Maintenance.tsx
 * (which doesn't exist yet — Phase 17 must ship self-contained). AI
 * Performance is the natural home regardless: retraining literally trains
 * the model this page reports on. Gated to Admin inline (this page is
 * otherwise Operator-visible, unlike the Users/Audit Log/Maintenance rows),
 * rather than a fourth ADMINISTRATION nav row — D-1 settled that group at
 * exactly three items.
 */
export function RetrainingExportPanel() {
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [cameraId, setCameraId] = useState("")

  const camerasQuery = useCameraOptions()
  const cameraOptions = [
    { value: "", label: "All cameras" },
    ...(camerasQuery.data?.cameras ?? []).map((c) => ({
      value: String(c.camera_id),
      label: c.camera_name,
    })),
  ]

  const track = useExportJobsStore((state) => state.track)

  // POST /api/exports/retraining is a different route and body shape than
  // the shared useExportJobSubmit hook's POST /exports/jobs (no
  // report_type field, format is always "zip") — a dedicated mutation,
  // tracked under the same store so the Phase 17 tray still picks it up.
  const jobMutation = useMutation({
    mutationFn: (params: RetrainingExportParams) => createRetrainingExport(params),
    onSuccess: (response) => {
      track({
        jobId: response.job_id,
        reportType: "retraining",
        format: "zip",
        createdAt: new Date().toISOString(),
      })
    },
  })

  function handleExport() {
    jobMutation.mutate({
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      camera_id: cameraId ? [Number(cameraId)] : undefined,
    })
  }

  return (
    <div className="mt-6 rounded-xl border border-stroke bg-surface-1 p-5">
      <h2 className="text-sm font-semibold text-fg">Retraining Export</h2>
      <p className="mt-1 text-caption text-fg-muted">
        Bundles confirmed and dismissed incidents in this range into a labelled training dataset for
        the AI engine — always a background job, always a ZIP.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2.5">
        <DateRangePicker
          start={startDate}
          end={endDate}
          onStartChange={setStartDate}
          onEndChange={setEndDate}
          label="Filter the retraining range by date"
        />
        <FilterSelect value={cameraId} options={cameraOptions} onChange={setCameraId} />
        <Button size="sm" isLoading={jobMutation.isPending} onClick={handleExport}>
          Export retraining package
        </Button>
      </div>

      {jobMutation.isError ? (
        <div className="mt-3">
          <QueryErrorBanner
            error={jobMutation.error}
            fallback="Unable to start the retraining export."
          />
        </div>
      ) : null}
    </div>
  )
}
