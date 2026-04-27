import api from "@/services/api"
import type {
  CameraListResponse,
  CameraRecord,
  CreateCameraInput,
  GetCamerasParams,
  UpdateCameraInput,
} from "@/types/cameras"

export async function getCameras(params: GetCamerasParams) {
  const { data } = await api.get<CameraListResponse>("/cameras/", {
    params,
  })

  return data
}

export async function createCamera(input: CreateCameraInput) {
  const { data } = await api.post<CameraRecord>("/cameras/", input)
  return data
}

export async function updateCamera(cameraId: number, input: UpdateCameraInput) {
  const { data } = await api.patch<CameraRecord>(`/cameras/${cameraId}`, input)
  return data
}

export async function deleteCamera(cameraId: number) {
  await api.delete(`/cameras/${cameraId}`)
}
