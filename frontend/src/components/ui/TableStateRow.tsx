import type { ReactNode } from "react"

import { cn } from "@/utils/cn"

/**
 * The loading / error / empty `<td colSpan>` row shared by the data tables.
 * Targets only the part that is identical across tables — columns, row actions
 * and cell styling stay page-specific.
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
          "px-6 py-8 text-center text-xs",
          tone === "error" ? "text-danger" : "text-fg-muted",
        )}
      >
        {children}
      </td>
    </tr>
  )
}
