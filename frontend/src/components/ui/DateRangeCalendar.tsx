import { RiArrowLeftSLine, RiArrowRightSLine } from "@remixicon/react"

import { cn } from "@/utils/cn"

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
]

const WEEKDAY_LABELS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]

function isoDateOf(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`
}

/**
 * A single-month range grid: pure and controlled, so DateRangePicker owns
 * the picking state machine (which click is the anchor, when a range is
 * complete) and this component only ever renders what it's told.
 */
export function DateRangeCalendar({
  viewYear,
  viewMonth,
  rangeStart,
  rangeEnd,
  today,
  onSelectDay,
  onPrevMonth,
  onNextMonth,
}: {
  viewYear: number
  /** 0-11 */
  viewMonth: number
  /** ISO `yyyy-mm-dd`, or null while no start has been picked yet. */
  rangeStart: string | null
  rangeEnd: string | null
  today: string
  onSelectDay: (isoDate: string) => void
  onPrevMonth: () => void
  onNextMonth: () => void
}) {
  const firstWeekday = new Date(viewYear, viewMonth, 1).getDay()
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()

  return (
    <div className="flex w-72 flex-col gap-3 p-4">
      <div className="flex items-center justify-between text-sm font-medium text-fg">
        <button
          type="button"
          onClick={onPrevMonth}
          aria-label="Previous month"
          className="flex rounded-md p-1 text-fg-muted hover:bg-surface-2 hover:text-fg"
        >
          <RiArrowLeftSLine size={16} aria-hidden="true" />
        </button>
        <span>
          {MONTH_NAMES[viewMonth]} {viewYear}
        </span>
        <button
          type="button"
          onClick={onNextMonth}
          aria-label="Next month"
          className="flex rounded-md p-1 text-fg-muted hover:bg-surface-2 hover:text-fg"
        >
          <RiArrowRightSLine size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-0.5">
        {WEEKDAY_LABELS.map((label, index) => (
          <div
            key={`${label}-${index}`}
            className="pb-1 text-center text-[10px] tracking-wide text-fg-muted"
          >
            {label}
          </div>
        ))}

        {Array.from({ length: firstWeekday }, (_, index) => (
          <div key={`blank-${index}`} />
        ))}

        {Array.from({ length: daysInMonth }, (_, index) => {
          const day = index + 1
          const iso = isoDateOf(viewYear, viewMonth, day)
          const isStart = iso === rangeStart
          const isEnd = iso === rangeEnd
          const isInRange = Boolean(rangeStart && rangeEnd && iso >= rangeStart && iso <= rangeEnd)
          const isToday = iso === today

          return (
            <button
              type="button"
              key={iso}
              onClick={() => onSelectDay(iso)}
              aria-label={`${MONTH_NAMES[viewMonth]} ${day}, ${viewYear}`}
              aria-pressed={isStart || isEnd}
              className={cn(
                "relative flex h-[30px] items-center justify-center rounded-md text-xs tabular-nums text-fg-body",
                isInRange && !isStart && !isEnd && "rounded-none bg-surface-2 text-fg",
                !isInRange && !isStart && !isEnd && "hover:bg-surface-2",
                isStart && !isEnd && "rounded-r-none",
                isEnd && !isStart && "rounded-l-none",
                (isStart || isEnd) && "bg-fg font-semibold text-fg-on-primary",
              )}
            >
              {day}
              {isToday && !isStart && !isEnd && (
                <span
                  aria-hidden="true"
                  className="absolute bottom-1 h-1 w-1 rounded-full bg-success"
                />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
