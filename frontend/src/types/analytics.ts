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
