import {
  RiBookOpenLine,
  RiCompassLine,
  RiPulseLine,
  RiQuestionLine,
  RiShieldUserLine,
  RiToolsLine,
} from "@remixicon/react"
import type { RemixiconComponentType } from "@remixicon/react"

/** Best-effort icon per category, echoing the icons the sidebar already uses
 * for the same concepts (System Health's RiPulseLine, etc.) — falls back to
 * the page's own book icon for a category this map doesn't know about, so a
 * newly-added category never renders with no icon at all. Shared between
 * CategoryTabs and ArticleGrid so both draw the same icon for a category. */
const CATEGORY_ICONS: Record<string, RemixiconComponentType> = {
  "Getting Started": RiCompassLine,
  Operations: RiToolsLine,
  Monitoring: RiPulseLine,
  Administration: RiShieldUserLine,
  FAQ: RiQuestionLine,
}

export function categoryIcon(category: string): RemixiconComponentType {
  return CATEGORY_ICONS[category] ?? RiBookOpenLine
}
