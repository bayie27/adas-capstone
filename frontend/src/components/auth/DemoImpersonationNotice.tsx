import { useQuery } from "@tanstack/react-query"

import { getMfaStatus } from "@/api/mfa"
import { useAuthStore } from "@/store/useAuthStore"

export function DemoImpersonationNotice() {
  const role = useAuthStore((state) => state.role)
  const { data } = useQuery({
    queryKey: ["auth", "mfa-status"],
    queryFn: getMfaStatus,
    enabled: Boolean(role),
    retry: false,
    staleTime: 0,
  })

  if (data?.auth_method !== "demo_impersonation") return null

  return (
    <div
      role="status"
      className="border-b border-warning/40 bg-warning/10 px-5 py-2 text-center text-caption font-semibold text-warning"
    >
      DEMO IMPERSONATION SESSION · security changes still require your password and authenticator
    </div>
  )
}
