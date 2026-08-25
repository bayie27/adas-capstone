import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { RiEditBoxLine, RiLockPasswordLine } from "@remixicon/react"

import { Badge, BadgeDot } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { getMyProfile } from "@/api/users"
import { useAuthStore } from "@/store/useAuthStore"
import { formatUserRole, getUserFullName, getUserInitials } from "@/utils/format"
import { formatShortDateTime, formatRelativeDateTime } from "@/utils/datetime"
import { ChangePasswordModal } from "@/pages/profile/ChangePasswordModal"
import { EditProfileModal } from "@/pages/profile/EditProfileModal"
import { AlarmSettingsCard } from "@/pages/profile/AlarmSettingsCard"
import { toast } from "@/store/useToastStore"

const PROFILE_QUERY_KEY = ["my-profile"] as const

type ModalState = { kind: "closed" } | { kind: "password" } | { kind: "edit_profile" }

export default function ProfileSettings() {
  const role = useAuthStore((state) => state.role)
  const username = useAuthStore((state) => state.username)
  const [modal, setModal] = useState<ModalState>({ kind: "closed" })

  const profileQuery = useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: getMyProfile,
  })

  const profile = profileQuery.data

  const displayName = useMemo(() => {
    if (profile) {
      return getUserFullName(profile)
    }
    return username || "User"
  }, [profile, username])

  const displayRole = formatUserRole(profile?.role ?? role)
  const initials = getUserInitials(
    profile?.first_name ?? "",
    profile?.last_name ?? "",
    profile?.username ?? username ?? "",
  )

  return (
    <div className="mx-auto max-w-4xl p-6 sm:p-8">
      <div className="mb-8">
        <h1 className="mb-0.5 text-xl font-semibold text-fg">Profile</h1>
        <p className="text-secondary text-fg-muted">
          Manage your personal information and system preferences.
        </p>
      </div>

      {profileQuery.isLoading ? (
        <div className="py-12 text-center text-secondary text-fg-muted">Loading profile...</div>
      ) : profileQuery.isError ? (
        <QueryErrorBanner
          error={profileQuery.error}
          fallback="Unable to load your profile."
          onRetry={() => profileQuery.refetch()}
        />
      ) : profile ? (
        <div className="divide-y divide-stroke">
          {/* Section 1: Avatar & Identity Header */}
          <div className="flex items-center gap-5 pb-8 sm:gap-6">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border border-stroke-strong bg-surface-2 text-h2 font-semibold text-fg shadow-inner sm:h-24 sm:w-24">
              {initials}
            </div>
            <div className="space-y-1">
              <h2 className="text-xl font-semibold text-fg sm:text-2xl">
                {displayName || "Unnamed User"}
              </h2>
              <p className="text-secondary text-fg-muted">{displayRole}</p>
              <p className="text-caption text-fg-muted">@{profile.username}</p>
            </div>
          </div>

          {/* Section 2: Personal Information */}
          <div className="py-8">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-fg sm:text-lg">Personal Information</h3>
              <button
                type="button"
                onClick={() => setModal({ kind: "edit_profile" })}
                className="flex items-center gap-1.5 rounded-lg border border-stroke bg-surface-2/40 px-3.5 py-1.5 text-secondary font-medium text-fg transition-colors hover:border-stroke-strong hover:bg-surface-2"
              >
                <span>Edit</span>
                <RiEditBoxLine size={16} className="text-fg-muted" />
              </button>
            </div>

            <div className="mt-6 grid grid-cols-1 gap-x-8 gap-y-6 sm:grid-cols-2">
              <div>
                <span className="text-caption text-fg-muted">First Name</span>
                <p className="mt-1 text-secondary font-medium text-fg">
                  {profile.first_name || "-"}
                </p>
              </div>

              <div>
                <span className="text-caption text-fg-muted">Last Name</span>
                <p className="mt-1 text-secondary font-medium text-fg">
                  {profile.last_name || "-"}
                </p>
              </div>

              <div>
                <span className="text-caption text-fg-muted">Role</span>
                <p className="mt-1 text-secondary font-medium text-fg">{displayRole}</p>
              </div>

              <div>
                <span className="text-caption text-fg-muted">Status</span>
                <div className="mt-1 flex items-center">
                  <Badge
                    tone={profile.is_active ? "success" : "neutral"}
                    variant="subtle"
                    icon={<BadgeDot tone={profile.is_active ? "success" : "neutral"} />}
                  >
                    {profile.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </div>

              <div>
                <span className="text-caption text-fg-muted">Username</span>
                <p className="mt-1 text-secondary font-medium text-fg">{profile.username}</p>
              </div>

              <div>
                <span className="text-caption text-fg-muted">Member Since</span>
                <p className="mt-1 text-secondary font-medium text-fg">
                  {formatShortDateTime(profile.created_at)}
                </p>
              </div>

              {profile.last_login ? (
                <div>
                  <span className="text-caption text-fg-muted">Last Login</span>
                  <p className="mt-1 text-secondary font-medium text-fg">
                    {formatRelativeDateTime(profile.last_login)}
                  </p>
                </div>
              ) : null}
            </div>
          </div>

          {/* Section 3: Security & Credentials */}
          <div className="flex flex-col items-start justify-between gap-4 py-8 sm:flex-row sm:items-center">
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-fg sm:text-lg">Security & Password</h3>
              <p className="text-secondary text-fg-muted">
                {profile.password_changed_at
                  ? `Password last changed ${formatRelativeDateTime(profile.password_changed_at)}.`
                  : "Keep your account secure with a strong password."}
              </p>
            </div>

            <Button
              variant="outline"
              onClick={() => setModal({ kind: "password" })}
              className="flex items-center gap-2"
            >
              <RiLockPasswordLine size={16} />
              <span>Change Password</span>
            </Button>
          </div>

          {/* Section 4: Alarm Settings */}
          <div className="pt-8">
            <AlarmSettingsCard className="border-0 bg-transparent p-0 shadow-none" />
          </div>

          {/* Modals */}
          {modal.kind === "edit_profile" && (
            <EditProfileModal profile={profile} onClose={() => setModal({ kind: "closed" })} />
          )}

          {modal.kind === "password" && (
            <ChangePasswordModal
              onClose={() => setModal({ kind: "closed" })}
              onSuccess={() => {
                toast.success("Password updated successfully.")
                setModal({ kind: "closed" })
              }}
            />
          )}
        </div>
      ) : null}
    </div>
  )
}
