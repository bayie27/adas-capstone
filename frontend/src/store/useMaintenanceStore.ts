import { create } from "zustand"

import type { MaintenanceNoticeData } from "@/api/events"

/**
 * Holds the most recent MAINTENANCE_NOTICE, in memory only — no
 * sessionStorage, no backend call. Dismissing just clears it; a fresh
 * envelope (a genuinely new restore, or a re-fire) sets it again regardless
 * of whether the last one was dismissed, so the operator is never left
 * silently un-warned about a second restore because they closed the first
 * notice. A reload starts from `notice: null` either way, since nothing here
 * persists.
 */
interface MaintenanceState {
  notice: MaintenanceNoticeData | null
  showNotice: (notice: MaintenanceNoticeData) => void
  dismiss: () => void
}

export const useMaintenanceStore = create<MaintenanceState>((set) => ({
  notice: null,
  showNotice: (notice) => set({ notice }),
  dismiss: () => set({ notice: null }),
}))
