import { useQuery } from "@tanstack/react-query"

import { getDevStatus, type DevProfileInfo } from "@/api/dev"

interface UseDevToolsResult {
  enabled: boolean
  profiles: DevProfileInfo[]
}

/**
 * Runtime probe for the dev-tools backend.
 *
 * Gated on this, deliberately NOT on `import.meta.env.DEV` (DT-3): the panel
 * has to work in a `pnpm build` bundle, because the LAN demo box serves a
 * production build and still needs it. `import.meta.env.DEV` is false there,
 * and there are no `import.meta.env.DEV` conditionals anywhere in this
 * codebase today — this is not the place to introduce the first one.
 *
 * The consequence is that the panel code ships in the production bundle,
 * which is why DevPanelTrigger lazy()-imports the panel body: it lands in
 * its own chunk and is never fetched unless the backend says the routes
 * exist.
 *
 * A 404 means the router was not registered, i.e. dev tools are off. retry
 * is disabled so that costs one request, and staleTime is Infinity because
 * the answer cannot change without a backend restart.
 *
 * Note that `queryClient.clear()` — which the post-reseed reset has to call,
 * since the app's query keys are ad-hoc across eight pages — drops this
 * entry too, and `enabled` would momentarily fall back to false, unmounting
 * the trigger and closing the panel mid-flow. DEV_STATUS_QUERY_KEY is
 * exported so the reset can write the probe result straight back after
 * clearing. gcTime does not help here: clear() empties the cache outright.
 */
export const DEV_STATUS_QUERY_KEY = ["dev-tools-status"] as const

export function useDevTools(): UseDevToolsResult {
  const { data } = useQuery({
    queryKey: DEV_STATUS_QUERY_KEY,
    queryFn: getDevStatus,
    retry: false,
    staleTime: Infinity,
  })

  return {
    enabled: data?.enabled ?? false,
    profiles: data?.profiles ?? [],
  }
}
