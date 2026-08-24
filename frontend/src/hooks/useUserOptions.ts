import { useQuery } from "@tanstack/react-query"

import { getUsers } from "@/api/users"

/**
 * Shared source for the user filter dropdown on Detections. Centralizing the
 * query keeps the item cap in exactly one place and the `staleTime` avoids
 * re-fetching a rarely-changing list on every visit.
 *
 * NOTE: silent cap — the backend has no unpaginated "options" endpoint, and
 * `GET /api/users/` caps `limit` at 100 (backend/app/api/routes/users.py), so
 * user #101 would not appear in the filter. The proper fix is a backend
 * `/users/options` route; this hook is the single call site to swap when it
 * lands.
 */
export function useUserOptions({
  enabled = true,
  isActive,
}: {
  enabled?: boolean
  isActive?: "true" | "false" | "null"
} = {}) {
  return useQuery({
    queryKey: ["users", "options", isActive],
    queryFn: () => getUsers({ limit: 100, is_active: isActive }),
    staleTime: 5 * 60_000,
    enabled,
  })
}
