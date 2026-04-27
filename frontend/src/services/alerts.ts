import api from "@/services/api"
import type { AlertListResponse, AlertLog, GetAlertsParams } from "@/types/alerts"
import { downloadBlobResponse } from "@/utils/download"

export async function getAlerts(params: GetAlertsParams) {
  const { data } = await api.get<AlertListResponse>("/alerts/", {
    params,
  })

  return data
}

export async function exportAlertsCsv(params: GetAlertsParams) {
  const response = await api.get<Blob>("/alerts/export", {
    params,
    responseType: "blob",
  })

  downloadBlobResponse(response, "adas_incident_export.csv")
}

export async function getAlertDetails(logId: number) {
  const { data } = await api.get<AlertLog>(`/alerts/${logId}`)
  return data
}

export async function confirmAlert(logId: number) {
  const { data } = await api.post<AlertLog>(`/alerts/${logId}/confirm`)
  return data
}

export async function dismissAlert(logId: number) {
  const { data } = await api.post<AlertLog>(`/alerts/${logId}/dismiss`)
  return data
}

export async function resolveAlert(logId: number) {
  const { data } = await api.post<AlertLog>(`/alerts/${logId}/resolve`)
  return data
}
