import type { ElementType } from "react"
import SearchLineIcon from "remixicon-react/SearchLineIcon"
import CalendarLineIcon from "remixicon-react/CalendarLineIcon"
import ArrowRightSLineIcon from "remixicon-react/ArrowRightSLineIcon"
import ArrowLeftSLineIcon from "remixicon-react/ArrowLeftSLineIcon"
import DownloadLineIcon from "remixicon-react/DownloadLineIcon"
import CarLineIcon from "remixicon-react/CarLineIcon"
import CloseCircleLineIcon from "remixicon-react/CloseCircleLineIcon"
import Focus3LineIcon from "remixicon-react/Focus3LineIcon"
import Dashboard3LineIcon from "remixicon-react/Dashboard3LineIcon"
import ArrowUpLineIcon from "remixicon-react/ArrowUpLineIcon"

const mockData = [
  { camera: "CROSSING - BANAY...", accidents: "10", dismissed: "5", precision: "50%", confidence: "81%", dismissedScore: "58%" },
  { camera: "AIRBASE - INTERSE...", accidents: "10", dismissed: "5", precision: "50%", confidence: "81%", dismissedScore: "58%" },
  { camera: "LTC - TAMBO", accidents: "10", dismissed: "5", precision: "50%", confidence: "81%", dismissedScore: "58%" },
]

interface PerfCardProps {
  icon: ElementType
  title: string
  value: string | number
  subtext?: string
  trend?: string
  trendUp?: boolean
}

function PerfCard({ icon: Icon, title, value, subtext, trend, trendUp = true }: PerfCardProps) {
  return (
    <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl p-5 flex flex-col justify-between h-full min-h-[160px]">
      <div>
        <div className="w-9 h-9 rounded-lg bg-[#1E1E1E] border border-[#2A2A2A] flex items-center justify-center mb-4">
          <Icon size={17} className="text-[#A1A1AA]" />
        </div>
        <h4 className="text-[#737373] text-[11px] font-medium uppercase tracking-wider mb-2 min-h-[32px]">{title}</h4>
        <div className="flex items-end gap-2.5 mb-1">
          <div className="text-3xl font-semibold text-white tracking-tight leading-none">{value}</div>
          {trend && (
            <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold mb-0.5 ${
              trendUp ? "text-[#ef4444] bg-[#ef4444]/10" : "text-emerald-500 bg-emerald-500/10"
            }`}>
              <ArrowUpLineIcon size={8} />
              {trend}
            </div>
          )}
        </div>
      </div>
      {subtext && (
        <div className="text-[#555] text-xs mt-4">{subtext}</div>
      )}
    </div>
  )
}

export default function AiPerformance() {
  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white mb-0.5">AI Performance</h1>
        <p className="text-[#737373] text-xs">Analyze confidence levels and track overall detection accuracy of cameras</p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
        <PerfCard
          icon={CarLineIcon}
          title="Total Accidents"
          value="446"
        />
        <PerfCard
          icon={CloseCircleLineIcon}
          title="Total Dismissed"
          value="5"
          trend="+12.5%"
          trendUp={true}
          subtext="Compared to last month"
        />
        <PerfCard
          icon={Focus3LineIcon}
          title="Avg Precision Score"
          value="50%"
          trend="+12.5%"
          trendUp={true}
          subtext="Compared to last month"
        />
        <PerfCard
          icon={Dashboard3LineIcon}
          title="Avg Confidence Score"
          value="81%"
          trend="+12.5%"
          trendUp={false}
          subtext="Compared to last month"
        />
        <PerfCard
          icon={CloseCircleLineIcon}
          title="Avg Dismissed Score"
          value="58%"
          trend="+12.5%"
          trendUp={true}
          subtext="Compared to last month"
        />
      </div>

      {/* Toolbar */}
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
        </div>
        <button className="flex items-center gap-2 px-3 py-1.5 bg-white text-black font-semibold rounded-md text-xs hover:bg-gray-100 transition-colors">
          <DownloadLineIcon size={13} />
          Export
        </button>
      </div>

      {/* Table */}
      <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#2A2A2A] text-[#737373] bg-[#141414]">
                <th className="px-6 py-4 font-medium text-xs">Camera Name</th>
                <th className="px-6 py-4 font-medium text-xs text-center">Accidents</th>
                <th className="px-6 py-4 font-medium text-xs text-center">Dismissed</th>
                <th className="px-6 py-4 font-medium text-xs text-center">Precision Score</th>
                <th className="px-6 py-4 font-medium text-xs text-center">Confidence Score</th>
                <th className="px-6 py-4 font-medium text-xs text-center">Dismissed Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2A2A2A]">
              {mockData.map((item, index) => (
                <tr key={index} className="text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
                  <td className="px-6 py-4 font-medium text-xs">{item.camera}</td>
                  <td className="px-6 py-4 text-xs text-center">{item.accidents}</td>
                  <td className="px-6 py-4 text-xs text-center">{item.dismissed}</td>
                  <td className="px-6 py-4 text-xs text-center text-[#ef4444] font-medium">{item.precision}</td>
                  <td className="px-6 py-4 text-xs text-center text-emerald-500 font-medium">{item.confidence}</td>
                  <td className="px-6 py-4 text-xs text-center text-[#ef4444] font-medium">{item.dismissedScore}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-[#2A2A2A] text-xs text-[#737373]">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              Items per page
              <button className="flex items-center gap-1 bg-[#141414] border border-[#2A2A2A] px-2 py-1 rounded text-white">
                3 <ArrowRightSLineIcon size={12} />
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
    </div>
  )
}
