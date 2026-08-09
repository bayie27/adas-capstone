import { useQuery } from "@tanstack/react-query"

import { getCameras } from "@/services/cameras"

/**
 * Shared source for the camera filter dropdowns on Dashboard, Detections and
 * AiPerformance. Centralizing the query keeps the item cap in exactly one place
 * and the `staleTime` stops those three pages from each re-fetching the same
 * rarely-changing list.
 *
 * NOTE: silent cap — the backend has no unpaginated "options" endpoint, and
 * `GET /api/cameras/` caps `limit` at 100 (backend/app/api/routes/cameras.py),
 * so camera #101 would not appear in any filter. The proper fix is a backend
 * `/cameras/options` route; this hook is the single call site to swap when it
 * lands.
 */
export function useCameraOptions() {
  return useQuery({
    queryKey: ["cameras", "options"],
    queryFn: () => getCameras({ limit: 100 }),
    staleTime: 5 * 60_000,
  })
}
