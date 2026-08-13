import api from "@/api/client"
import { downloadBlobResponse } from "@/utils/download"

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

export async function exportDashboardAnalyticsCsv(params: AnalyticsFilters = {}) {
  const response = await api.get<Blob>("/analytics/export/dashboard", {
    params,
    responseType: "blob",
  })

  downloadBlobResponse(response, "adas_dashboard_export.csv")
}

export async function exportPerformanceAnalyticsCsv(params: PerformanceAnalyticsFilters = {}) {
  const response = await api.get<Blob>("/analytics/export/performance", {
    params,
    responseType: "blob",
  })

  downloadBlobResponse(response, "adas_performance_export.csv")
}
