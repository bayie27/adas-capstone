import api from "@/api/client"
import { downloadBlobResponse } from "@/utils/download"
import type { ExportFormat } from "@/components/ui/ExportButton"

export interface DashboardAnalyticsKpis {
  ongoing: number
  total_accidents: number
  total_cleared: number
  /**
   * Percentage change against the previous window of the same duration,
   * with the same camera filter applied (`schemas/analytics.py:15-17`).
   * `null` whenever there's no previous window to compare against: the
   * default all-time load (both dates unset), a half-open range (only one
   * date set), or a previous window that was itself zero (growth from
   * nothing isn't a percentage an operator can act on). Never render `null`
   * as 0% -- those are different facts.
   */
  ongoing_delta_pct: number | null
  total_accidents_delta_pct: number | null
  total_cleared_delta_pct: number | null
}

export interface DashboardLocationFrequency {
  camera_name: string
  accident_count: number
}

export interface DashboardPeakAccidentTime {
  hour: number
  count: number
}

export interface DashboardAnalyticsResponse {
  kpis: DashboardAnalyticsKpis
  frequency_by_location: DashboardLocationFrequency[]
  peak_accident_times: DashboardPeakAccidentTime[]
}

export interface PerformanceGlobalKpis {
  total_accidents: number
  total_dismissed: number
  precision_score: number | null
  avg_accident_confidence: number | null
  avg_dismissed_confidence: number | null
}

export interface PerformanceCameraStat {
  camera_id: number
  camera_name: string
  total_accidents: number
  total_dismissed: number
  precision_score: number | null
  avg_accident_confidence: number | null
  avg_dismissed_confidence: number | null
}

export interface PerformanceAnalyticsResponse {
  global_kpis: PerformanceGlobalKpis
  // P19 §4 (breaking) — total rows matching the filters, NOT len(per_camera).
  // per_camera is one page (default limit=10), not the full array.
  total_filtered: number
  per_camera: PerformanceCameraStat[]
}

export interface AnalyticsFilters {
  start_date?: string
  end_date?: string
  camera_id?: number[]
}

export interface PerformanceAnalyticsFilters extends AnalyticsFilters {
  search?: string
  limit?: number
  offset?: number
}

export async function getDashboardAnalytics(params: AnalyticsFilters = {}) {
  const { data } = await api.get<DashboardAnalyticsResponse>("/analytics/dashboard", {
    params,
  })

  return data
}

export async function getPerformanceAnalytics(params: PerformanceAnalyticsFilters = {}) {
  const { data } = await api.get<PerformanceAnalyticsResponse>("/analytics/performance", {
    params,
  })

  return data
}

/**
 * `GET /api/analytics/export/dashboard` accepts `?format=csv|pdf`
 * (`analytics.py:252`) and enforces the same row-count ceiling as every other
 * export route. This was `exportDashboardAnalyticsCsv(params)` — a name and a
 * signature that both forbade PDF on a route that has always accepted it.
 *
 * Unlike the incident export, this screen cannot supply a pre-flight row
 * count: `GET /api/analytics/dashboard` returns aggregates, not a filtered row
 * count. The 413 this can still throw is not an omission — the export route
 * counts the underlying rows regardless of what the dashboard displays.
 */
export async function exportDashboardAnalytics(
  params: AnalyticsFilters = {},
  format: ExportFormat = "csv",
) {
  const response = await api.get<Blob>("/analytics/export/dashboard", {
    params: { ...params, format },
    responseType: "blob",
  })

  downloadBlobResponse(response, `adas_dashboard_export.${format}`)
}

/**
 * `GET /api/analytics/export/performance` accepts `?format=csv|pdf`, the
 * same as every other export route. This was `exportPerformanceAnalyticsCsv`
 * — a name and signature that both forbade PDF on a route that always
 * accepted it.
 */
export async function exportPerformanceAnalytics(
  params: PerformanceAnalyticsFilters = {},
  format: ExportFormat = "csv",
) {
  const response = await api.get<Blob>("/analytics/export/performance", {
    params: { ...params, format },
    responseType: "blob",
  })

  downloadBlobResponse(response, `adas_performance_export.${format}`)
}
