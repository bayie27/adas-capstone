import { Modal } from "@/components/ui/Modal"
import { BadgeDot } from "@/components/ui/Badge"
import { RiInformationLine } from "@remixicon/react"

interface HealthMetricsReferenceModalProps {
  isOpen: boolean
  onClose: () => void
}

const AI_PROCESSING_TIME_THRESHOLDS = [
  {
    tone: "success" as const,
    state: "Optimal",
    range: "15–45ms",
    meaning: "Fast enough for real-time processing without queuing or frame drops",
  },
  {
    tone: "warning" as const,
    state: "Acceptable",
    range: "45–70ms",
    meaning: "Still operating in real-time, but near the upper threshold for optimal performance",
  },
  {
    tone: "neutral" as const,
    state: "Idle",
    range: "N/A",
    meaning: "Expected when 0 cameras are connected",
  },
  {
    tone: "danger" as const,
    state: "Fault",
    range: "Engine error",
    meaning: "Cameras active, but AI engine failed or is unreachable",
  },
]

const PROCESSING_SPEED_THRESHOLDS = [
  {
    tone: "success" as const,
    state: "Optimal",
    range: "10.0–15.0 fps",
    meaning: "Matches the system's calibrated target band for accurate accident detection",
  },
  {
    tone: "warning" as const,
    state: "Low FPS",
    range: "Below 10.0 fps",
    meaning: "Stream lagging or camera/hardware constrained",
  },
  {
    tone: "neutral" as const,
    state: "Idle",
    range: "N/A",
    meaning: "Expected when no camera streams are active",
  },
  {
    tone: "danger" as const,
    state: "Fault",
    range: "Stream error",
    meaning: "Camera connected, but streaming has stalled",
  },
]

export function HealthMetricsReferenceModal({ isOpen, onClose }: HealthMetricsReferenceModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Performance Metrics Reference"
      subtitle="Threshold breakdown and operational status indicators for camera processing and AI detection."
      className="max-w-2xl"
    >
      <div className="flex flex-col gap-6 pt-2">
        {/* AI Processing Time Section */}
        <div>
          <h4 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-fg">
            <RiInformationLine size={16} className="text-fg-muted" aria-hidden="true" />
            AI Processing Time
          </h4>
          <div className="overflow-hidden rounded border border-stroke bg-surface-2">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-stroke bg-surface-3/50 font-medium text-fg-muted">
                <tr>
                  <th className="px-3 py-2">State</th>
                  <th className="px-3 py-2">Range</th>
                  <th className="px-3 py-2">Meaning</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stroke text-fg-body">
                {AI_PROCESSING_TIME_THRESHOLDS.map((row) => (
                  <tr key={row.state} className="transition-colors hover:bg-surface-3/30">
                    <td className="whitespace-nowrap px-3 py-2 font-medium text-fg">
                      <span className="inline-flex items-center gap-2">
                        <BadgeDot tone={row.tone} />
                        {row.state}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px]">
                      {row.range}
                    </td>
                    <td className="px-3 py-2 text-fg-muted">{row.meaning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Processing Speed Section */}
        <div>
          <h4 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-fg">
            <RiInformationLine size={16} className="text-fg-muted" aria-hidden="true" />
            Processing Speed
          </h4>
          <div className="overflow-hidden rounded border border-stroke bg-surface-2">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-stroke bg-surface-3/50 font-medium text-fg-muted">
                <tr>
                  <th className="px-3 py-2">State</th>
                  <th className="px-3 py-2">Range</th>
                  <th className="px-3 py-2">Meaning</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stroke text-fg-body">
                {PROCESSING_SPEED_THRESHOLDS.map((row) => (
                  <tr key={row.state} className="transition-colors hover:bg-surface-3/30">
                    <td className="whitespace-nowrap px-3 py-2 font-medium text-fg">
                      <span className="inline-flex items-center gap-2">
                        <BadgeDot tone={row.tone} />
                        {row.state}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px]">
                      {row.range}
                    </td>
                    <td className="px-3 py-2 text-fg-muted">{row.meaning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Modal>
  )
}
