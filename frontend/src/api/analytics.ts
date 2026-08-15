import api from "@/api/client"
import { downloadBlobResponse } from "@/utils/download"
import type { ExportFormat } from "@/components/ui/ExportButton"

export interface DashboardAnalyticsKpis {
  ongoing: number
  total_accidents: number
  total_resolved: number
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
  per_camera: PerformanceCameraStat[]
}

export interface AnalyticsFilters {
  start_date?: string
  end_date?: string
  camera_id?: number[]
}

export interface PerformanceAnalyticsFilters extends AnalyticsFilters {
  search?: string
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

export async function exportPerformanceAnalyticsCsv(params: PerformanceAnalyticsFilters = {}) {
  const response = await api.get<Blob>("/analytics/export/performance", {
    params,
    responseType: "blob",
  })

  downloadBlobResponse(response, "adas_performance_export.csv")
}
