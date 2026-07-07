import ArrowRightLineIcon from "remixicon-react/ArrowRightLineIcon"
import BookOpenLineIcon from "remixicon-react/BookOpenLineIcon"
import CustomerService2LineIcon from "remixicon-react/CustomerService2LineIcon"
import FileList3LineIcon from "remixicon-react/FileList3LineIcon"
import LifebuoyLineIcon from "remixicon-react/LifebuoyLineIcon"
import ShieldCheckLineIcon from "remixicon-react/ShieldCheckLineIcon"
import SignalTowerLineIcon from "remixicon-react/SignalTowerLineIcon"
import TimeLineIcon from "remixicon-react/TimeLineIcon"

const quickLinks = [
  {
    title: "Alert workflow",
    detail: "Confirm, dismiss, resolve, and audit detection records.",
    icon: ShieldCheckLineIcon,
  },
  {
    title: "Camera issues",
    detail: "Check stream status, AI status, and channel assignments.",
    icon: SignalTowerLineIcon,
  },
  {
    title: "Account access",
    detail: "Reset passwords, manage roles, and recover operator access.",
    icon: LifebuoyLineIcon,
  },
]

const procedures = [
  "Verify the active camera and confidence score before confirming an alert.",
  "Use Dismiss only when the snapshot clearly shows no accident event.",
  "Resolve confirmed alerts after response teams have closed the incident.",
  "Report repeated camera disconnects with the camera name and channel ID.",
]

export default function HelpCenter() {
  return (
    <div className="min-h-screen bg-[#0A0A0A] px-8 py-8 text-[#D4D4D4]">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b border-[#2A2A2A] pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-[#737373]">
              Support Desk
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-white">Help Center</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#A1A1AA]">
              Quick operating references for ADAS users handling detections, camera health, and account access.
            </p>
          </div>
          <div className="rounded-lg border border-[#2A2A2A] bg-[#111111] px-4 py-3 text-sm">
            <div className="flex items-center gap-2 text-white">
              <TimeLineIcon size={16} className="text-[#A1A1AA]" />
              Response target
            </div>
            <p className="mt-1 text-xs text-[#737373]">Critical system issues: within 15 minutes</p>
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-3">
          {quickLinks.map((item) => (
            <article key={item.title} className="rounded-xl border border-[#2A2A2A] bg-[#111111] p-5">
              <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-lg border border-[#2A2A2A] bg-[#1E1E1E]">
                <item.icon size={18} className="text-[#D4D4D4]" />
              </div>
              <h2 className="text-base font-semibold text-white">{item.title}</h2>
              <p className="mt-2 min-h-[44px] text-sm leading-6 text-[#737373]">{item.detail}</p>
              <button className="mt-5 flex items-center gap-2 text-sm font-medium text-white">
                View guide <ArrowRightLineIcon size={16} />
              </button>
            </article>
          ))}
        </section>

        <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-xl border border-[#2A2A2A] bg-[#111111] p-6">
            <div className="mb-5 flex items-center gap-3">
              <BookOpenLineIcon size={18} className="text-[#A1A1AA]" />
              <h2 className="text-lg font-semibold text-white">Operator procedure</h2>
            </div>
            <div className="space-y-3">
              {procedures.map((procedure, index) => (
                <div key={procedure} className="flex gap-3 rounded-lg border border-[#242424] bg-[#151515] p-4">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#242424] text-xs font-semibold text-white">
                    {index + 1}
                  </span>
                  <p className="text-sm leading-6 text-[#A1A1AA]">{procedure}</p>
                </div>
              ))}
            </div>
          </div>

          <aside className="rounded-xl border border-[#2A2A2A] bg-[#111111] p-6">
            <div className="mb-5 flex items-center gap-3">
              <CustomerService2LineIcon size={18} className="text-[#A1A1AA]" />
              <h2 className="text-lg font-semibold text-white">Contact support</h2>
            </div>
            <div className="space-y-4 text-sm text-[#A1A1AA]">
              <p>For urgent detection or camera failures, contact the system administrator with the page, camera, and time observed.</p>
              <div className="rounded-lg border border-[#242424] bg-[#151515] p-4">
                <div className="flex items-center gap-2 text-white">
                  <FileList3LineIcon size={16} className="text-[#A1A1AA]" />
                  Include in report
                </div>
                <p className="mt-2 text-xs leading-5 text-[#737373]">
                  Username, camera name, channel ID, alert ID, and a short description of what failed.
                </p>
              </div>
            </div>
          </aside>
        </section>
      </div>
    </div>
  )
}