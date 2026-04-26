import { useState } from "react"
import EyeLineIcon from "remixicon-react/EyeLineIcon"
import ArrowRightSLineIcon from "remixicon-react/ArrowRightSLineIcon"
import ArrowLeftSLineIcon from "remixicon-react/ArrowLeftSLineIcon"
import CloseLineIcon from "remixicon-react/CloseLineIcon"
import SearchLineIcon from "remixicon-react/SearchLineIcon"
import CalendarLineIcon from "remixicon-react/CalendarLineIcon"
import DownloadLineIcon from "remixicon-react/DownloadLineIcon"
import { Modal } from "@/components/Modal"
import { cn } from "@/utils"

const mockOngoing = [
  {
    id: "ACC-000002",
    timestamp: "2026-03-12 01:17:09",
    camera: "AIR BASE - INTERSECTION",
    status: "Ongoing",
    handler: "Juan De La Cruz",
    updated: "2026-03-12 01:17:10",
    confidence: "63%"
  }
]

const mockLogs = [
  {
    id: "ACC-000002",
    timestamp: "2026-03-12 01:17:09",
    camera: "AIR BASE - INTERSECTION",
    status: "Resolved",
    handler: "Jose Del Pilar",
    updated: "2026-03-12 02:11:03",
    confidence: "63%",
    closedBy: "Jose Del Pilar",
    timeResolved: "2026-03-12 02:11:03"
  },
  {
    id: "ACC-000001",
    timestamp: "2026-03-11 07:03:12",
    camera: "LIPA TOWN CENTER",
    status: "Dismissed",
    handler: "Juan De La Cruz",
    updated: "-",
    confidence: "42%",
    closedBy: "Juan De La Cruz",
    timeResolved: "2026-03-11 07:05:00"
  }
]

interface Accident {
  id: string
  timestamp: string
  camera: string
  status: string
  handler: string
  updated: string
  confidence: string
  closedBy?: string
  timeResolved?: string
}

export default function Detections() {
  const [activeTab, setActiveTab] = useState<"ongoing" | "logs">("ongoing")
  const [selectedAccident, setSelectedAccident] = useState<Accident | null>(null)

  const currentData = activeTab === "ongoing" ? mockOngoing : mockLogs

  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white mb-0.5">Detections</h1>
        <p className="text-[#737373] text-xs">Monitor ongoing AI detections and review historical logs to verify reported incidents</p>
      </div>

      <div className="flex items-center gap-2 bg-[#141414] border border-[#2A2A2A] rounded-md p-1 w-fit mb-6">
        <button
          onClick={() => setActiveTab("ongoing")}
          className={cn(
            "px-5 py-1.5 rounded text-xs font-medium transition-all duration-200",
            activeTab === "ongoing" ? "bg-[#1A1A1A] text-white shadow-sm border border-[#333]" : "text-[#737373] hover:text-[#D4D4D4]"
          )}
        >
          Ongoing
        </button>
        <button
          onClick={() => setActiveTab("logs")}
          className={cn(
            "px-5 py-1.5 rounded text-xs font-medium transition-all duration-200",
            activeTab === "logs" ? "bg-[#1A1A1A] text-white shadow-sm border border-[#333]" : "text-[#737373] hover:text-[#D4D4D4]"
          )}
        >
          Logs
        </button>
      </div>

      {activeTab === "logs" && (
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div className="flex items-center gap-2.5">
            <div className="relative">
              <SearchLineIcon size={14} className="text-[#555] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search..."
                className="bg-[#141414] border border-[#2A2A2A] rounded-md text-xs text-white pl-8 pr-4 py-1.5 w-60 focus:outline-none focus:border-[#52525B]"
              />
            </div>
            <button className="flex items-center gap-2 px-3 py-1.5 bg-[#141414] border border-[#2A2A2A] rounded-md text-xs text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
              <CalendarLineIcon size={13} className="text-[#737373]" />
              March 11, 2026 - March 14, 2026
            </button>
            <button className="flex items-center gap-1.5 px-3 py-1.5 bg-[#141414] border border-[#2A2A2A] rounded-md text-xs text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
              Camera Name
              <ArrowRightSLineIcon size={13} className="text-[#737373]" />
            </button>
            <button className="flex items-center gap-1.5 px-3 py-1.5 bg-[#141414] border border-[#2A2A2A] rounded-md text-xs text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
              Status
              <ArrowRightSLineIcon size={13} className="text-[#737373]" />
            </button>
            <button className="flex items-center gap-1.5 px-3 py-1.5 bg-[#141414] border border-[#2A2A2A] rounded-md text-xs text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
              Operator
              <ArrowRightSLineIcon size={13} className="text-[#737373]" />
            </button>
          </div>
          <button className="flex items-center gap-2 px-3 py-1.5 bg-white text-black font-semibold rounded-md text-xs hover:bg-gray-100 transition-colors">
            <DownloadLineIcon size={13} />
            Export
          </button>
        </div>
      )}

      <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#2A2A2A] text-[#737373] bg-[#141414]">
                <th className="px-6 py-4 font-medium text-xs">Accident No.</th>
                <th className="px-6 py-4 font-medium text-xs">Timestamp</th>
                <th className="px-6 py-4 font-medium text-xs">Camera Name</th>
                <th className="px-6 py-4 font-medium text-xs">Status</th>
                <th className="px-6 py-4 font-medium text-xs">Last Handled By</th>
                <th className="px-6 py-4 font-medium text-xs">Last Updated</th>
                <th className="px-6 py-4 font-medium text-xs text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2A2A2A]">
              {currentData.map((item) => (
                <tr key={item.id} className="text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
                  <td className="px-6 py-4 text-xs font-medium">{item.id}</td>
                  <td className="px-6 py-4 text-xs text-[#737373]">{item.timestamp}</td>
                  <td className="px-6 py-4 text-xs">{item.camera}</td>
                  <td className="px-6 py-4 text-xs">
                    <span className={cn(
                      "font-medium",
                      item.status === "Ongoing" ? "text-amber-500" :
                        item.status === "Resolved" ? "text-emerald-500" : "text-[#737373]"
                    )}>
                      {item.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-xs text-[#737373]">{item.handler}</td>
                  <td className="px-6 py-4 text-xs text-[#737373]">{item.updated}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end">
                      <button
                        onClick={() => setSelectedAccident(item)}
                        className="w-7 h-7 rounded border border-[#333] flex items-center justify-center bg-[#1A1A1A] hover:bg-[#2A2A2A] transition-colors"
                      >
                        <EyeLineIcon size={14} className="text-white" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between px-6 py-3 border-t border-[#2A2A2A] text-xs text-[#737373]">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              Items per page
              <button className="flex items-center gap-1 bg-[#141414] border border-[#2A2A2A] px-2 py-1 rounded text-white">
                {currentData.length} <ArrowRightSLineIcon size={12} />
              </button>
            </div>
            <span>1-10 of {currentData.length}</span>
          </div>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-1 hover:text-white transition-colors">
              <ArrowLeftSLineIcon size={14} /> Previous
            </button>
            <div className="flex items-center gap-1">
              <button className="w-5 h-5 rounded bg-[#1E1E1E] text-white flex items-center justify-center font-medium">1</button>
              <button className="w-5 h-5 rounded hover:bg-[#1A1A1A] flex items-center justify-center text-[#A1A1AA]">2</button>
              <button className="w-5 h-5 rounded hover:bg-[#1A1A1A] flex items-center justify-center text-[#A1A1AA]">3</button>
              <span className="text-[#555]">...</span>
            </div>
            <button className="flex items-center gap-1 hover:text-white transition-colors">
              Next <ArrowRightSLineIcon size={14} />
            </button>
          </div>
        </div>
      </div>

      <Modal
        isOpen={!!selectedAccident}
        onClose={() => setSelectedAccident(null)}
        className={cn(
          "p-0 overflow-hidden max-w-lg border-t-4",
          selectedAccident?.status === "Ongoing" ? "border-t-amber-500" : "border-t-[#E4E4E7]"
        )}
      >
        <div className="bg-[#18181B] flex flex-col">
          <div className="flex items-center justify-between px-6 py-4 border-b border-[#27272A]">
            <h2 className="text-white font-semibold tracking-wider text-xs uppercase">ACCIDENT DETAILS</h2>
            <button onClick={() => setSelectedAccident(null)} className="text-[#737373] hover:text-white transition-colors">
              <CloseLineIcon size={18} />
            </button>
          </div>

          <div className="bg-[#111] aspect-video w-full flex items-center justify-center border-b border-[#2A2A2A]">
            <div className="w-48 h-32 border border-[#333] bg-[#1A1A1A] flex items-center justify-center text-xs text-[#555]">Preview</div>
          </div>

          <div className="p-6">
            <div className="flex items-center gap-3 mb-5">
              <span className="text-xl font-semibold text-white">{selectedAccident?.id}</span>
              <span className={cn(
                "text-[10px] font-bold px-2 py-0.5 rounded-sm uppercase tracking-wider",
                selectedAccident?.status === "Ongoing" ? "bg-amber-500 text-black" : "bg-[#E4E4E7] text-black"
              )}>
                {selectedAccident?.status === "Ongoing" ? "ONGOING" : "RESOLVED"}
              </span>
            </div>

            <div className="space-y-3.5 mb-6">
              <div className="flex justify-between items-center text-xs">
                <span className="text-[#737373] font-medium tracking-wider">TIMESTAMP</span>
                <span className="text-[#D4D4D4] font-medium">{selectedAccident?.timestamp}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-[#737373] font-medium tracking-wider">CAMERA NAME</span>
                <span className="text-[#D4D4D4] font-medium">{selectedAccident?.camera}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-[#737373] font-medium tracking-wider">AI-CONFIDENCE SCORE</span>
                <span className="text-[#ef4444] font-bold bg-[#ef4444]/10 px-1.5 py-0.5 rounded">{selectedAccident?.confidence}</span>
              </div>
            </div>

            <div className="border-t border-[#27272A] pt-5 mb-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <div className="text-[#555] text-[10px] font-bold tracking-widest mb-1.5 uppercase">VERIFIED BY</div>
                  <div className="text-[#D4D4D4] text-xs font-medium">Juan De La Cruz</div>
                </div>
                <div className="text-right">
                  <div className="text-[#555] text-[10px] font-bold tracking-widest mb-1.5 uppercase">TIME VERIFIED</div>
                  <div className="text-[#D4D4D4] text-xs">2026-03-12 01:17:10</div>
                </div>
              </div>

              {selectedAccident?.status !== "Ongoing" && (
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-[#555] text-[10px] font-bold tracking-widest mb-1.5 uppercase">CLOSED BY</div>
                    <div className="text-[#D4D4D4] text-xs font-medium">{selectedAccident?.closedBy}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[#555] text-[10px] font-bold tracking-widest mb-1.5 uppercase">TIME RESOLVED</div>
                    <div className="text-[#D4D4D4] text-xs">{selectedAccident?.timeResolved}</div>
                  </div>
                </div>
              )}
            </div>

            {selectedAccident?.status === "Ongoing" && (
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSelectedAccident(null)}
                  className="flex-1 bg-[#1A1A1A] hover:bg-[#2A2A2A] border border-[#333] text-white text-xs font-medium py-2.5 rounded-md transition-colors uppercase tracking-wider"
                >
                  Dismiss Accident
                </button>
                <button
                  className="flex-1 bg-white hover:bg-gray-100 text-black text-xs font-semibold py-2.5 rounded-md transition-colors uppercase tracking-wider"
                >
                  Resolve Accident
                </button>
              </div>
            )}
          </div>
        </div>
      </Modal>
    </div>
  )
}
