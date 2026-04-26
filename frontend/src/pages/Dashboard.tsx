import type { ElementType } from "react"
import CalendarLineIcon from "remixicon-react/CalendarLineIcon"
import ArrowRightSLineIcon from "remixicon-react/ArrowRightSLineIcon"
import DownloadLineIcon from "remixicon-react/DownloadLineIcon"
import RefreshLineIcon from "remixicon-react/RefreshLineIcon"
import CarLineIcon from "remixicon-react/CarLineIcon"
import CheckboxLineIcon from "remixicon-react/CheckboxLineIcon"
import ArrowUpLineIcon from "remixicon-react/ArrowUpLineIcon"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  Tooltip,
} from "recharts"

const lineData = [
  { time: '0', value: 30 },
  { time: '2', value: 45 },
  { time: '4', value: 90 },
  { time: '6', value: 45 },
  { time: '8', value: 65 },
  { time: '10', value: 50 },
  { time: '12', value: 85 },
  { time: '14', value: 40 },
  { time: '16', value: 65 },
  { time: '18', value: 40 },
  { time: '20', value: 60 },
  { time: '22', value: 95 },
  { time: '24', value: 55 },
]

const barData = [
  { name: 'CROSSING - ...', value: 100 },
  { name: 'LTO - TAMBO', value: 65 },
  { name: 'MONUMENTO', value: 50 },
  { name: 'SICO PETRON', value: 42 },
  { name: 'SABANG SHELL', value: 35 },
  { name: 'SANAYBANAY...', value: 20 },
  { name: 'AYALA MCDO', value: 18 },
  { name: 'MR BASE - IN...', value: 14 },
  { name: 'TAMBO JOLLI...', value: 12 },
  { name: 'LIPA CITY HALL', value: 8 },
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
    <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl p-5 flex flex-col justify-between h-full">
      <div>
        <div className="w-9 h-9 rounded-lg bg-[#1E1E1E] border border-[#2A2A2A] flex items-center justify-center mb-5">
          <Icon size={17} className="text-[#A1A1AA]" />
        </div>
        <h4 className="text-[#737373] text-xs mb-2">{title}</h4>
        <div className="text-[28px] font-semibold text-white tracking-tight leading-none">{value}</div>
      </div>
      {subtext && trend && (
        <div className="flex items-center justify-between mt-5">
          <span className="text-[#555] text-xs">{subtext}</span>
          <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${trendUp ? "text-[#ef4444] bg-[#ef4444]/10" : "text-emerald-500 bg-emerald-500/10"
            }`}>
            <ArrowUpLineIcon size={10} />
            {trend}
          </div>
        </div>
      )}
    </div>
  )
}

export default function Dashboard() {
  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white mb-0.5">Dashboard</h1>
        <p className="text-[#737373] text-xs">View analytical summaries & peak accident trends</p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-2.5">
          <button className="flex items-center gap-2 px-3 py-1.5 bg-[#141414] border border-[#2A2A2A] rounded-md text-xs text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
            <CalendarLineIcon size={13} className="text-[#737373]" />
            March 11, 2026 – March 14, 2026
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

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        <div className="lg:col-span-3 flex flex-col gap-5">

          <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl p-5 h-[260px] flex flex-col">
            <h3 className="text-[#D4D4D4] text-xs font-medium mb-4">Peak Accident Hours (24H)</h3>
            <div className="flex-1 -ml-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={lineData}>
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ffffff" stopOpacity={0.08} />
                      <stop offset="95%" stopColor="#ffffff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E1E1E" vertical={false} />
                  <XAxis
                    dataKey="time"
                    stroke="#333"
                    tick={{ fill: '#555', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    dy={8}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1A1A1A', border: '1px solid #2A2A2A', borderRadius: '6px', fontSize: 12 }}
                    itemStyle={{ color: '#E4E4E7' }}
                    labelStyle={{ color: '#737373' }}
                    cursor={{ stroke: '#333', strokeWidth: 1 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#fff"
                    strokeWidth={1.5}
                    dot={(props: { cx?: number, cy?: number, payload?: { time: string } }) => {
                      if (props.payload?.time === '12') {
                        return <circle cx={props.cx} cy={props.cy} r={3.5} fill="#fff" stroke="#111" strokeWidth={2} />
                      }
                      return null as unknown as React.ReactElement
                    }}
                    activeDot={{ r: 4, fill: "#fff" }}
                    fillOpacity={1}
                    fill="url(#colorValue)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl p-5 h-[330px] flex flex-col">
            <h3 className="text-[#D4D4D4] text-xs font-medium mb-4">Accident Frequency by Location</h3>
            <div className="flex-1 -ml-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                  <XAxis
                    type="number"
                    stroke="#333"
                    tick={{ fill: '#555', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    dy={8}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke="#333"
                    tick={{ fill: '#737373', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={98}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1A1A1A', border: '1px solid #2A2A2A', borderRadius: '6px', fontSize: 12 }}
                    itemStyle={{ color: '#E4E4E7' }}
                    labelStyle={{ color: '#737373' }}
                    cursor={{ fill: '#1E1E1E' }}
                  />
                  <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={14}>
                    {barData.map((_entry, index) => (
                      <Cell key={`cell-${index}`} fill={index === 0 ? '#737373' : '#2A2A2A'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>

        <div className="flex flex-col gap-5">
          <div className="h-[160px]">
            <MetricCard
              icon={RefreshLineIcon}
              title="Ongoing Accidents"
              value="3"
            />
          </div>
          <div className="h-[195px]">
            <MetricCard
              icon={CarLineIcon}
              title="Total Accidents"
              value="132"
              subtext="Compared to last month"
              trend="+12.5%"
              trendUp={true}
            />
          </div>
          <div className="h-[195px]">
            <MetricCard
              icon={CheckboxLineIcon}
              title="Total Resolve"
              value="132"
              subtext="Compared to last month"
              trend="+12.5%"
              trendUp={true}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
