import type { ElementType, ReactNode } from "react"

interface StatCardProps {
  icon: ElementType
  title: string
  value: ReactNode
  subtext?: string
  delta?: string
  deltaPositive?: boolean
}

export function StatCard({
  icon: Icon,
  title,
  value,
  subtext,
  delta,
  deltaPositive,
}: StatCardProps) {
  return (
    <div className="flex h-full min-h-[160px] flex-col justify-between rounded-xl border border-stroke bg-surface-1 p-5">
      <div>
        <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg border border-stroke bg-surface-2">
          <Icon size={17} className="text-fg-muted" />
        </div>
        <h4 className="mb-2 min-h-[32px] text-[11px] font-medium uppercase tracking-wider text-fg-muted">
          {title}
        </h4>
        <div className="flex items-end gap-2.5">
          <div className="text-3xl font-semibold leading-none tracking-tight text-fg">{value}</div>
          {delta ? (
            <span
              className={`mb-1 text-xs font-medium ${deltaPositive ? "text-success" : "text-danger"}`}
            >
              {delta}
            </span>
          ) : null}
        </div>
      </div>
      {subtext ? <div className="mt-4 text-xs text-fg-muted">{subtext}</div> : null}
    </div>
  )
}
