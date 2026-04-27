import api from "@/services/api"
import type {
  AnalyticsFilters,
  DashboardAnalyticsResponse,
  PerformanceAnalyticsFilters,
  PerformanceAnalyticsResponse,
} from "@/types/analytics"
import { downloadBlobResponse } from "@/utils/download"

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
