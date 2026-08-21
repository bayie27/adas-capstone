import re

with open("frontend/src/pages/AiPerformance.tsx") as f:
    content = f.read()

# Add imports
imports = """
import { useRef, useEffect } from "react"
import { getAlerts } from "@/api/alerts"
import { createRetrainingExport, type RetrainingExportParams } from "@/api/exports"
import { useExportJobsStore } from "@/store/useExportJobsStore"
import { Modal } from "@/components/ui/Modal"
import { Button } from "@/components/ui/Button"
import { RiArrowDownSLine, RiDownloadLine, RiAlertLine } from "@remixicon/react"
"""
# find the first import line and insert
content = re.sub(r"(import .*?\n)", r"\1" + imports.strip() + "\n", content, count=1)

# we need to remove ExportButton from imports? We'll let eslint fix it if it's unused.

# Replace the component body starts
hooks = """
  const [showWarningModal, setShowWarningModal] = useState(false)
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false)
  const menuContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isExportMenuOpen) return
    const handleClick = (e: MouseEvent) => {
      if (!menuContainerRef.current?.contains(e.target as Node)) {
        setIsExportMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [isExportMenuOpen])

  const track = useExportJobsStore((state) => state.track)

  const labelledCountQuery = useQuery({
    queryKey: ["retraining-labelled-count", startDate, endDate, cameraId],
    queryFn: () =>
      getAlerts({
        status: ["Resolved", "Dismissed"],
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        camera_id: cameraId ? [Number(cameraId)] : undefined,
        limit: 1,
      }),
  })
  const labelledCount = labelledCountQuery.data?.total_filtered

  const retrainingJobMutation = useMutation({
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

  function handleRetrainingExportClick() {
    setIsExportMenuOpen(false)
    if (labelledCount !== undefined && labelledCount < 50) {
      setShowWarningModal(true)
    } else {
      executeRetrainingExport()
    }
  }

  function executeRetrainingExport() {
    setShowWarningModal(false)
    retrainingJobMutation.mutate({
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      camera_id: cameraId ? [Number(cameraId)] : undefined,
    })
  }
"""
content = content.replace(
    "const exportJobMutation = useExportJobSubmit()",
    "const exportJobMutation = useExportJobSubmit()\n" + hooks,
)

dropdown_jsx = """
        <div className="relative" ref={menuContainerRef}>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsExportMenuOpen(!isExportMenuOpen)}
            isLoading={exportMutation.isPending || exportJobMutation.isPending || retrainingJobMutation.isPending}
            loadingLabel="Exporting..."
          >
            <RiDownloadLine size={13} />
            Export
            <RiArrowDownSLine size={14} />
          </Button>

          {isExportMenuOpen && (
            <div className="absolute right-0 top-full mt-1 z-50 w-64 rounded-md border border-stroke bg-surface-1 py-1 shadow-overlay">
              <div className="px-3 py-1.5 text-xs font-semibold text-fg-muted">Performance Report</div>
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-xs text-fg-body hover:bg-surface-2"
                onClick={() => { setIsExportMenuOpen(false); exportJobMutation.mutateAsync({ report_type: "performance", format: "csv", search: debouncedSearchTerm || undefined, start_date: startDate || undefined, end_date: endDate || undefined, camera_id: cameraId ? [Number(cameraId)] : undefined }) }}
              >
                Export as CSV
              </button>
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-xs text-fg-body hover:bg-surface-2"
                onClick={() => { setIsExportMenuOpen(false); exportJobMutation.mutateAsync({ report_type: "performance", format: "pdf", search: debouncedSearchTerm || undefined, start_date: startDate || undefined, end_date: endDate || undefined, camera_id: cameraId ? [Number(cameraId)] : undefined }) }}
              >
                Export as PDF
              </button>

              {role === "Admin" && (
                <>
                  <div className="my-1 border-t border-stroke" />
                  <div className="px-3 py-1.5 text-xs font-semibold text-fg-muted">Training Data</div>
                  <button
                    type="button"
                    className="w-full px-3 py-2 text-left text-xs text-fg-body hover:bg-surface-2"
                    onClick={handleRetrainingExportClick}
                  >
                    Export Retraining Dataset (ZIP)
                  </button>
                </>
              )}
            </div>
          )}
        </div>
"""

old_export_button = """        <ExportButton
          rowCount={totalFiltered}
          isExporting={exportMutation.isPending}
          exportHasError={exportMutation.isError}
          onExport={(format) => exportMutation.mutate(format)}
          isSubmittingJob={exportJobMutation.isPending}
          onExportJob={(format) =>
            exportJobMutation.mutateAsync({
              report_type: "performance",
              format,
              search: debouncedSearchTerm || undefined,
              start_date: startDate || undefined,
              end_date: endDate || undefined,
              camera_id: cameraId ? [Number(cameraId)] : undefined,
            })
          }
        />"""

content = content.replace(old_export_button, dropdown_jsx)

modal_jsx = """
      {retrainingJobMutation.isError ? (
        <QueryErrorBanner
          error={retrainingJobMutation.error}
          fallback="Unable to start the retraining export job."
        />
      ) : null}

      <div className="overflow-hidden rounded-xl border border-stroke bg-surface-1">
"""
content = content.replace(
    '      <div className="overflow-hidden rounded-xl border border-stroke bg-surface-1">',
    modal_jsx,
)

modal_bottom = """
      <Modal
        open={showWarningModal}
        onClose={() => setShowWarningModal(false)}
        title=""
        description=""
      >
        <div className="flex flex-col items-center gap-4 text-center">
          <RiAlertLine size={48} className="text-warning" />
          <div className="space-y-2">
            <h3 className="text-lg font-semibold text-fg">Dataset Too Small</h3>
            <p className="text-sm font-normal leading-relaxed text-fg-muted">
              {new Intl.NumberFormat("en-US").format(labelledCount ?? 0)} labelled incident{(labelledCount ?? 0) === 1 ? "" : "s"} in this range.
              Exporting fewer than 50 wastes a training run — widen the range or camera filter first.
            </p>
          </div>
        </div>
        <div className="flex w-full justify-end gap-2 mt-4">
          <Button variant="outline" onClick={() => setShowWarningModal(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={executeRetrainingExport}>
            Export Anyway
          </Button>
        </div>
      </Modal>
    </div>
  )
}
"""
content = content.replace("    </div>\n  )\n}", modal_bottom)

with open("frontend/src/pages/AiPerformance.tsx", "w") as f:
    f.write(content)
