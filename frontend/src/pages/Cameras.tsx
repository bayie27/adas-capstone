import { useState, type ElementType } from "react"
import CameraLineIcon from "remixicon-react/CameraLineIcon"
import GlobalLineIcon from "remixicon-react/GlobalLineIcon"
import RobotLineIcon from "remixicon-react/RobotLineIcon"
import SearchLineIcon from "remixicon-react/SearchLineIcon"
import ArrowRightSLineIcon from "remixicon-react/ArrowRightSLineIcon"
import AddLineIcon from "remixicon-react/AddLineIcon"
import PencilLineIcon from "remixicon-react/PencilLineIcon"
import DeleteBinLineIcon from "remixicon-react/DeleteBinLineIcon"
import AlertLineIcon from "remixicon-react/AlertLineIcon"
import ArrowLeftSLineIcon from "remixicon-react/ArrowLeftSLineIcon"
import ArrowUpLineIcon from "remixicon-react/ArrowUpLineIcon"
import { Modal } from "@/components/Modal"
import { cn } from "@/utils"

interface Camera {
  id: number
  name: string
  url: string
  connection: string
  ai: string
  active: boolean
}

// --- Mock Data ---
const mockCameras: Camera[] = [
  { id: 1, name: "CROSSING - BANAYBANAY", url: "rtsp://admin:password123@1...", connection: "Connected", ai: "Pause", active: true },
  { id: 2, name: "AIR BASE - INTERSECTION", url: "rtsp://admin:password123@1...", connection: "Connected", ai: "Inactive", active: false },
  { id: 3, name: "LTC - TAMBO", url: "rtsp://admin:password123@1...", connection: "Connected", ai: "Active", active: true },
  { id: 4, name: "AYALA MCDO", url: "rtsp://admin:password123@1...", connection: "Connected", ai: "Active", active: true },
  { id: 5, name: "LIPA CITY HALL", url: "rtsp://admin:password123@1...", connection: "Connected", ai: "Active", active: true },
  { id: 6, name: "TAMBO JOLLIBEE", url: "rtsp://admin:password123@1...", connection: "Connected", ai: "Active", active: true },
  { id: 7, name: "SABANG SHELL", url: "rtsp://admin:password123@1...", connection: "Connected", ai: "Active", active: true },
  { id: 8, name: "SICO PETRON", url: "rtsp://admin:password123@1...", connection: "Connected", ai: "Active", active: true },
  { id: 9, name: "MONUMENTO", url: "rtsp://admin:password123@1...", connection: "Connected", ai: "Active", active: true },
]

interface MetricCardProps {
  icon: ElementType
  title: string
  value: string | number
  subtext?: string
  trend?: string
  trendUp?: boolean
}

function MetricCard({ icon: Icon, title, value, subtext, trend, trendUp = true }: MetricCardProps) {
  return (
    <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl p-5 flex flex-col justify-between h-[160px]">
      <div>
        <div className="w-9 h-9 rounded-lg bg-[#1E1E1E] border border-[#2A2A2A] flex items-center justify-center mb-4">
          <Icon size={17} className="text-[#A1A1AA]" />
        </div>
        <div className="flex items-center justify-between mb-1.5">
          <h4 className="text-[#737373] text-xs">{title}</h4>
          {trend && (
            <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold ${trendUp ? "text-emerald-500 bg-emerald-500/10" : "text-[#ef4444] bg-[#ef4444]/10"
              }`}>
              <ArrowUpLineIcon size={8} />
              {trend}
            </div>
          )}
        </div>
        <div className="text-[28px] font-semibold text-white tracking-tight leading-none">{value}</div>
      </div>
      {subtext && (
        <div className="text-[#555] text-xs mt-3">{subtext}</div>
      )}
    </div>
  )
}

function Switch({ checked, onChange }: { checked: boolean, onChange?: () => void }) {
  return (
    <button
      type="button"
      onClick={onChange}
      aria-pressed={checked}
      className={cn(
        "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
        checked ? "bg-white" : "bg-[#3f3f46]"
      )}
    >
      <span
        className={cn(
          "inline-block h-3.5 w-3.5 transform rounded-full bg-[#18181b] transition-transform",
          checked ? "translate-x-4" : "translate-x-1"
        )}
      />
    </button>
  )
}

export default function Cameras() {
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null)

  const openEdit = (cam: Camera) => {
    setSelectedCamera(cam)
    setIsEditOpen(true)
  }

  const openDelete = (cam: Camera) => {
    setSelectedCamera(cam)
    setIsDeleteOpen(true)
  }

  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white mb-0.5">Camera Management</h1>
        <p className="text-[#737373] text-xs">Add, configure, and monitor the connection and AI detection status of cameras</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        <MetricCard
          icon={CameraLineIcon}
          title="Total Cameras"
          value="446"
        />
        <MetricCard
          icon={GlobalLineIcon}
          title="Network Connected Cameras"
          value="132"
          subtext="Compared to last month"
          trend="+12.5%"
          trendUp={true}
        />
        <MetricCard
          icon={RobotLineIcon}
          title="Active Detection Cameras"
          value="131"
          subtext="Compared to last month"
          trend="+12.5%"
          trendUp={true}
        />
      </div>

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
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-[#141414] border border-[#2A2A2A] rounded-md text-xs text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
            Network Connection
            <ArrowRightSLineIcon size={13} className="text-[#737373]" />
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-[#141414] border border-[#2A2A2A] rounded-md text-xs text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
            AI Detection Status
            <ArrowRightSLineIcon size={13} className="text-[#737373]" />
          </button>
        </div>
        <button
          onClick={() => setIsAddOpen(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white text-black font-semibold rounded-md text-xs hover:bg-gray-100 transition-colors"
        >
          <AddLineIcon size={14} />
          Add Camera
        </button>
      </div>

      {/* Table */}
      <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#2A2A2A] text-[#737373] bg-[#141414]">
                <th className="px-6 py-4 font-medium text-xs">Camera Name</th>
                <th className="px-6 py-4 font-medium text-xs">Stream URL (RTSP)</th>
                <th className="px-6 py-4 font-medium text-xs">Connection Status</th>
                <th className="px-6 py-4 font-medium text-xs">AI Detection Status</th>
                <th className="px-6 py-4 font-medium text-xs text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2A2A2A]">
              {mockCameras.map((cam) => (
                <tr key={cam.id} className="text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
                  <td className="px-6 py-4 text-xs font-medium">{cam.name}</td>
                  <td className="px-6 py-4 text-xs text-[#737373]">{cam.url}</td>
                  <td className="px-6 py-4 text-xs">
                    <span className={cn("font-medium", cam.connection === "Connected" ? "text-emerald-500" : "text-red-500")}>
                      {cam.connection}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-xs">
                    <span className={cn(
                      "font-medium",
                      cam.ai === "Active" ? "text-emerald-500" :
                        cam.ai === "Pause" ? "text-amber-500" : "text-red-500"
                    )}>
                      {cam.ai}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-3">
                      <Switch checked={cam.active} />
                      <button onClick={() => openEdit(cam)} className="text-[#737373] hover:text-white transition-colors">
                        <PencilLineIcon size={14} />
                      </button>
                      <button onClick={() => openDelete(cam)} className="text-[#737373] hover:text-white transition-colors">
                        <DeleteBinLineIcon size={14} />
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
                8 <ArrowRightSLineIcon size={12} />
              </button>
            </div>
            <span>1-10 of 446</span>
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
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        title="Add Camera"
        subtitle="Assign name and select the channel no. of the camera"
        icon={<div className="w-10 h-10 rounded-full border border-[#333] flex items-center justify-center bg-transparent"><CameraLineIcon size={20} className="text-white" /></div>}
      >
        <div className="space-y-4 mt-2">
          <div>
            <label className="block text-xs font-semibold text-white mb-2">Camera name</label>
            <input
              type="text"
              placeholder="Rizal Street"
              className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555] placeholder-[#555]"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-white mb-2">Channel No.</label>
            <input
              type="text"
              placeholder="1"
              className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555] placeholder-[#555]"
            />
          </div>
          <div className="flex items-center justify-end gap-3 mt-8">
            <button onClick={() => setIsAddOpen(false)} className="px-4 py-2 border border-[#333] rounded-md text-sm font-medium text-[#E4E4E7] hover:text-white transition-colors bg-transparent">
              Cancel
            </button>
            <button className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-gray-100 transition-colors">
              Save Changes
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit Camera Modal */}
      <Modal
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        title="Edit Camera"
        subtitle="Update existing camera name & channel no."
        icon={<div className="w-10 h-10 rounded-full border border-[#333] flex items-center justify-center bg-transparent"><PencilLineIcon size={20} className="text-white" /></div>}
      >
        <div className="space-y-4 mt-2">
          <div>
            <label className="block text-xs font-semibold text-white mb-2">Camera name</label>
            <input
              type="text"
              defaultValue={selectedCamera?.name}
              className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555]"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-white mb-2">Channel No.</label>
            <input
              type="text"
              defaultValue="1"
              className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555]"
            />
          </div>

          <div className="flex items-end justify-between mt-8">
            <div className="text-[10px] text-[#71717A] space-y-1">
              <div>Date Added: 2025-03-12</div>
              <div>Last Changes:</div>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => setIsEditOpen(false)} className="px-4 py-2 border border-[#333] rounded-md text-sm font-medium text-[#E4E4E7] hover:text-white transition-colors bg-transparent">
                Cancel
              </button>
              <button className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-gray-100 transition-colors">
                Save Changes
              </button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        hideClose
      >
        <div className="flex flex-col items-center pt-6 text-center">
          <AlertLineIcon size={36} className="text-[#ef4444] mb-4" />
          <h3 className="text-[15px] font-bold text-white mb-2">Are you absolutely sure?</h3>
          <p className="text-[11px] text-[#A1A1AA] leading-relaxed mb-6 px-4">
            This action cannot be undone. This will permanently delete camera "{selectedCamera?.name}" and remove the data from the server.
          </p>
          <div className="flex items-center justify-end gap-3 w-full">
            <button onClick={() => setIsDeleteOpen(false)} className="px-4 py-2 border border-[#333] rounded-md text-xs font-semibold text-white hover:bg-[#1A1A1A] transition-colors bg-transparent">
              Cancel
            </button>
            <button className="px-4 py-2 bg-white text-black rounded-md text-xs font-semibold hover:bg-gray-100 transition-colors">
              Continue
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
