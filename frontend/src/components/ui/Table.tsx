import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from "react"
import { RiArrowDownSLine, RiArrowUpSLine } from "@remixicon/react"

import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

/**
 * The table container and its parts, as the Cameras / Detections / Users /
 * AI Performance frames draw them: a --radius-sm (4px) card with the table inside,
 * caption-sized muted headers (12px), --color-stroke row dividers, and 24px cell
 * padding (§2.3).
 *
 * §2.7 — tables scroll horizontally inside their card rather than reflowing.
 * There is no card-per-row mobile table and no design for one; this is a
 * desk-bound operator console.
 */
export function TableContainer({
  className,
  footer,
  children,
}: {
  className?: string
  /**
   * Rendered inside the card but *outside* the horizontal scroll area — the
   * pagination footer the frames draw stays put while a wide table scrolls
   * under it.
   */
  footer?: ReactNode
  children: ReactNode
}) {
  return (
    <div className={cn("overflow-hidden rounded-sm border border-stroke bg-surface-1", className)}>
      <div className="overflow-x-auto">{children}</div>
      {footer}
    </div>
  )
}

export function Table({ className, children }: { className?: string; children: ReactNode }) {
  return <table className={cn("w-full text-left", className)}>{children}</table>
}

export function TableHead({ children }: { children: ReactNode }) {
  return (
    <thead className="border-b border-stroke">
      <tr>{children}</tr>
    </thead>
  )
}

export interface ColumnSort {
  /**
   * The backend sort key. **Must** be a member of the route's allowlist —
   * `ALERT_SORT_FIELDS` (9 values) or `AUDIT_SORT_FIELDS` (6). An unlisted
   * value is a 422, so a caller must take this from the exported allowlist
   * rather than deriving it from a column label or an element id.
   */
  key: string
  /** `null` when some other column is the active sort. */
  active: "asc" | "desc" | null
  onSort: (key: string) => void
}

export function TableHeaderCell({
  className,
  children,
  sort,
  ...rest
}: ThHTMLAttributes<HTMLTableCellElement> & { sort?: ColumnSort }) {
  const base = cn("px-6 py-4 text-caption font-medium text-fg-muted", className)

  if (!sort) {
    return (
      <th className={base} {...rest}>
        {children}
      </th>
    )
  }

  const Chevron = sort.active === "asc" ? RiArrowUpSLine : RiArrowDownSLine

  return (
    <th
      className={base}
      // "none" rather than omitting the attribute: it tells a screen reader
      // the column is sortable and currently unsorted, which is exactly the
      // affordance the visual resting state withholds.
      aria-sort={
        sort.active === "asc" ? "ascending" : sort.active === "desc" ? "descending" : "none"
      }
      {...rest}
    >
      <button
        type="button"
        onClick={() => sort.onSort(sort.key)}
        className={cn(
          "group -mx-1 flex w-full items-center gap-1 rounded-sm px-1 text-left",
          "transition-colors duration-150 hover:text-fg-body",
          focusRing,
          className?.includes("text-right") && "justify-end",
        )}
      >
        {children}
        {/*
          D-8(a). Two states, not three: a click toggles asc/desc and there is
          no third click that clears. The table always has a sort — omitting
          `sort_by` just means `detected_at desc`, which is a sort like any
          other, and a third state that silently reverts to a *different*
          column's order is a worse affordance than not having one.

          The active column shows a solid chevron. An inactive sortable column
          shows one only on hover or keyboard focus: three columns each
          carrying a permanent dimmed glyph reads as three sort controls all
          half-on, but a column with no affordance at all is undiscoverable —
          and on this table, sorting by confidence_score is the detector-audit
          tool, so it has to be findable.
        */}
        <Chevron
          size={14}
          aria-hidden
          className={cn(
            "shrink-0 transition-opacity duration-150",
            sort.active
              ? "text-fg opacity-100"
              : "opacity-0 group-hover:opacity-60 group-focus-visible:opacity-60",
          )}
        />
      </button>
    </th>
  )
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>
}

/** §2.8 — row hover is --color-surface-1's nearest neighbour on the elevated scale. */
export function TableRow({
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        "border-b border-stroke transition-colors duration-150 last:border-0 hover:bg-surface-2",
        className,
      )}
      {...rest}
    >
      {children}
    </tr>
  )
}

export function TableCell({
  className,
  children,
  ...rest
}: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn("px-6 py-4 text-secondary text-fg-body", className)} {...rest}>
      {children}
    </td>
  )
}

/**
 * The loading / empty / error row, absorbed from the old TableStateRow so the
 * three §2.8 body states live with the table they fill. Targets only the part
 * that is identical across tables — columns, row actions and cell styling stay
 * page-specific.
 */
export function TableStateRow({
  colSpan,
  tone = "muted",
  children,
}: {
  colSpan: number
  tone?: "muted" | "error"
  children: ReactNode
}) {
  return (
    <tr>
      <td
        colSpan={colSpan}
        className={cn(
          "px-6 py-8 text-center text-caption",
          tone === "error" ? "text-danger" : "text-fg-muted",
        )}
      >
        {children}
      </td>
    </tr>
  )
}
