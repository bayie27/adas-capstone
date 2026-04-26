import { useState, useEffect, type ElementType } from "react"
import ServerLineIcon from "remixicon-react/ServerLineIcon"
import TimerLineIcon from "remixicon-react/TimerLineIcon"
import Dashboard3LineIcon from "remixicon-react/Dashboard3LineIcon"
import HardDrive2LineIcon from "remixicon-react/HardDrive2LineIcon"
import ArrowUpLineIcon from "remixicon-react/ArrowUpLineIcon"
import {
  AreaChart,
  Area,
  XAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts"

const chartData = [
  { time: '0', usage: 12 },
  { time: '2', usage: 18 },
  { time: '4', usage: 15 },
  { time: '6', usage: 22 },
  { time: '8', usage: 30 },
  { time: '10', usage: 25 },
  { time: '12', usage: 45 },
  { time: '14', usage: 28 },
  { time: '16', usage: 35 },
  { time: '18', usage: 20 },
  { time: '20', usage: 30 },
  { time: '22', usage: 40 },
  { time: '24', usage: 25 },
]

interface HealthCardProps {
  icon: ElementType
  title: string
  value: string | number
  subtext?: string
  trend?: string
  trendUp?: boolean
}

function HealthCard({ icon: Icon, title, value, subtext, trend, trendUp = true }: HealthCardProps) {
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
            <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold mb-0.5 ${trendUp ? "text-[#ef4444] bg-[#ef4444]/10" : "text-emerald-500 bg-emerald-500/10"
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

interface ChartData {
  time: string
  usage: number
}

interface HealthChartProps {
  title: string
  data: ChartData[]
  dataKey: string
  color: string
}

function HealthChart({ title, data, dataKey, color }: HealthChartProps) {
  return (
    <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl p-5 h-[260px] flex flex-col">
      <h3 className="text-[#D4D4D4] text-xs font-medium mb-4">{title}</h3>
      <div className="flex-1 -ml-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id={`color-${title.replace(/\s+/g, '')}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.15} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1E1E1E" vertical={false} />
            <XAxis dataKey="time" stroke="#333" tick={{ fill: '#555', fontSize: 11 }} axisLine={false} tickLine={false} dy={8} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1A1A1A', border: '1px solid #2A2A2A', borderRadius: '6px', fontSize: 12 }}
              itemStyle={{ color: '#E4E4E7' }}
              labelStyle={{ color: '#737373' }}
            />
            <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5} fillOpacity={1} fill={`url(#color-${title.replace(/\s+/g, '')})`} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default function SystemHealth() {
  const [uptime, setUptime] = useState("0d 00h 00m")

  useEffect(() => {
    const start = new Date("2026-03-01T00:00:00")
    const timer = setInterval(() => {
      const now = new Date()
      const diff = now.getTime() - start.getTime()
      const d = Math.floor(diff / (1000 * 60 * 60 * 24))
      const h = Math.floor((diff / (1000 * 60 * 60)) % 24)
      const m = Math.floor((diff / (1000 * 60)) % 60)
      setUptime(`${d}d ${h.toString().padStart(2, '0')}h ${m.toString().padStart(2, '0')}m`)
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  const [activeTab, setActiveTab] = useState<"48h" | "30d">("48h")

  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white mb-0.5">System Health</h1>
        <p className="text-[#737373] text-xs">Oversee system diagnostics and hardware performance</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <HealthCard
          icon={ServerLineIcon}
          title="Server Uptime"
          value={uptime}
        />
        <HealthCard
          icon={TimerLineIcon}
          title="Inference Latency"
          value="46ms"
          trend="+12.5%"
          trendUp={true}
          subtext="Compared to last month"
        />
        <HealthCard
          icon={Dashboard3LineIcon}
          title="Processing Speed"
          value="13fps"
          trend="+12.5%"
          trendUp={false}
          subtext="Compared to last month"
        />
        <HealthCard
          icon={HardDrive2LineIcon}
          title="Disk Storage Usage"
          value="28%"
          subtext="128gb / 256gb"
        />
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4 mb-5">
        <button
          onClick={() => setActiveTab("48h")}
          className={`text-xs font-medium px-4 py-1.5 rounded-full transition-colors ${activeTab === "48h" ? "bg-[#1E1E1E] text-white border border-[#333]" : "text-[#737373] hover:text-[#D4D4D4]"
            }`}
        >
          Last 48 Hours
        </button>
        <button
          onClick={() => setActiveTab("30d")}
          className={`text-xs font-medium px-4 py-1.5 rounded-full transition-colors ${activeTab === "30d" ? "bg-[#1E1E1E] text-white border border-[#333]" : "text-[#737373] hover:text-[#D4D4D4]"
            }`}
        >
          30-Day Trend
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <HealthChart
          title="CPU Utilization"
          data={chartData}
          dataKey="usage"
          color="#ffffff"
        />
        <HealthChart
          title="GPU Utilization"
          data={chartData}
          dataKey="usage"
          color="#ffffff"
        />
        <HealthChart
          title="Core Temperature"
          data={chartData}
          dataKey="usage"
          color="#ffffff"
        />
        <HealthChart
          title="Active RAM"
          data={chartData}
          dataKey="usage"
          color="#ffffff"
        />
      </div>
    </div>
  )
}
