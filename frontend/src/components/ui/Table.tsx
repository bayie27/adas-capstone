import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from "react"

import { cn } from "@/utils/cn"

/**
 * The table container and its parts, as the Cameras / Detections / Users /
 * AI Performance frames draw them: a --radius-xl card with the table inside,
 * caption-sized muted headers, --color-stroke row dividers, and 24px cell
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
    <div className={cn("overflow-hidden rounded-xl border border-stroke bg-surface-1", className)}>
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

export function TableHeaderCell({
  className,
  children,
  ...rest
}: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={cn("px-6 py-4 text-caption font-medium text-fg-muted", className)} {...rest}>
      {children}
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
